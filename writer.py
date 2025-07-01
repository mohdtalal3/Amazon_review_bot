import os
import time
import json
import re
from PyQt5.QtCore import QThread, pyqtSignal
from openai import OpenAI
from utils import setup_google_sheets

class ReviewWriter(QThread):
    update_status = pyqtSignal(str)
    
    def __init__(self, credentials_file, sheet_id, api_key, batch_size=10):
        super().__init__()
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.api_key = api_key
        self.batch_size = batch_size
        self.prompt_template = self.load_prompt_template()
    
    def load_prompt_template(self):
        """Load the prompt template from review_prompt.txt file"""
        try:
            prompt_file_path = os.path.join(os.path.dirname(__file__), 'review_prompt.txt')
            with open(prompt_file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            # Fallback to hardcoded prompt if file not found
            return """You are a helpful product reviewer who writes authentic, short Amazon reviews based on real-life usage. Your reviews sound like they were written by a real person who actually used the product in day-to-day life. 

Every review should:
- Sound like you're talking to someone casually.  
- Be short, useful, and straight to the point.
- Never describe the product features directly or repeat details from the product listing.
- Never use marketing words like "game-changer," "must-have," "life-changing," or any other AI-sounding fluff.
- Never promote the product.
- Never use dashes in any sentence.
- Never say "recently" or write like you're telling a story about a new thing you got.
- Never sound robotic or formal.
- Be written like someone in 9th grade but still helpful and grounded.
- Avoid repeating the product name in the review. Just get into your thoughts on it.

For each product below, generate:
1. A short "headline" (written in Title Case) that sounds casual and human.
2. A detailed "review" (80–120 words) that sticks to the rules above.

Write the output as a JSON array in the following format:
[
{{
    "headline": "Perfect Shade For Poolside And Backyard Lounging",
    "review": "This umbrella has made our backyard way more enjoyable on sunny afternoons..."
}},
...
]

---

Now, based on the following input, write reviews:

{PRODUCTS_DATA}"""
        except Exception as e:
            print(f"Error loading prompt template: {e}")
            # Return fallback prompt
            return """You are a helpful product reviewer who writes authentic, short Amazon reviews based on real-life usage.

{PRODUCTS_DATA}"""
        
    # Function to clean JSON response that might be wrapped in markdown code blocks
    def clean_json_response(self, response_text):
        # Check if the response is wrapped in markdown code blocks
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        match = re.search(code_block_pattern, response_text)
        
        if match:
            # Extract the JSON content from the code block
            return match.group(1).strip()
        
        # If no code block is found, return the original text
        return response_text
        
    def run(self):
        try:
            # Set up Google Sheets
            self.update_status.emit("Setting up Google Sheets...")
            leads_sheet, processed_sheet, not_processed_sheet = setup_google_sheets(
                self.credentials_file, 
                self.sheet_id,
                self.update_status.emit
            )
            
            if not leads_sheet:
                self.update_status.emit("Failed to set up Google Sheets. Exiting.")
                return
            
            # Initialize the OpenAI client
            client = OpenAI(api_key=self.api_key)
            
            # Get all rows from leads sheet
            all_values = leads_sheet.get_all_values()
            if len(all_values) <= 1:  # Only headers or empty
                self.update_status.emit("No reviews to process in Google Sheet.")
                return
                
            headers = all_values[0]
            
            # Find column indices
            try:
                review_idx = headers.index("Review")
                headline_idx = headers.index("Headline")
                product_name_idx = headers.index("Product_name")
                product_idx = headers.index("Product")
                asin_idx = headers.index("Asin")
                date_idx = headers.index("Date")
            except ValueError as e:
                self.update_status.emit(f"Error finding required columns: {str(e)}")
                return
            
            # Process rows in batches
            rows_to_process = all_values[1:]  # Skip header row
            total_rows = len(rows_to_process)
            self.update_status.emit(f"Found {total_rows} rows to process")
            
            # Process in batches
            for start in range(0, total_rows, self.batch_size):
                end = min(start + self.batch_size, total_rows)
                batch = rows_to_process[start:end]
                
                # Identify rows without reviews or headlines
                batch_to_review = []
                batch_indices = []
                
                for i, row in enumerate(batch):
                    review_value = row[review_idx] if review_idx < len(row) else ""
                    headline_value = row[headline_idx] if headline_idx < len(row) else ""
                    
                    # Only process if both review AND headline are empty
                    if not review_value.strip() and not headline_value.strip():
                        batch_to_review.append(row)
                        batch_indices.append(i + start + 2)  # +2 for 1-indexed rows in sheet and to skip header
                
                if not batch_to_review:
                    self.update_status.emit(f"Batch {start+1}-{end}: No reviews to generate")
                    continue
                
                self.update_status.emit(f"Processing batch {start+1}-{end}, generating {len(batch_to_review)} reviews...")
                
                # Prepare product data for the prompt
                products = []
                for row in batch_to_review:
                    product_name = ""
                    if product_name_idx < len(row) and row[product_name_idx].strip():
                        product_name = row[product_name_idx]
                    elif product_idx < len(row) and row[product_idx].strip():
                        product_name = row[product_idx]
                    
                    asin = row[asin_idx] if asin_idx < len(row) else ""
                    date = row[date_idx] if date_idx < len(row) else ""
                    
                    # Only add if we have a product name
                    if product_name.strip():
                        products.append({
                            "product_name": product_name,
                            "asin": asin,
                            "date": date
                        })
                
                # Skip if no valid products found
                if not products:
                    self.update_status.emit(f"Batch {start+1}-{end}: No valid products found")
                    continue
                
                # Construct the prompt using the template from file
                prompt = self.prompt_template.replace("{PRODUCTS_DATA}", json.dumps(products, indent=2))

                
                try:
                    # Call the OpenAI API
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that writes Amazon Vine-style product reviews."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.5
                    )
                    
                    # Get the response content
                    response_content = response.choices[0].message.content
                    self.update_status.emit(f"Received response, parsing JSON...")
                    
                    try:
                        # Clean the response content if it contains markdown code blocks
                        cleaned_content = self.clean_json_response(response_content)
                        
                        # Parse the cleaned response content
                        generated_reviews = json.loads(cleaned_content)
                        
                        # Prepare batch update for Google Sheets
                        self.update_status.emit(f"Preparing batch update for {len(generated_reviews)} reviews...")
                        
                        # Get all current sheet data 
                        current_data = leads_sheet.get_all_values()
                        
                        # Create a batch update list
                        batch_updates = []
                        
                        for i, review in enumerate(generated_reviews):
                            if i < len(batch_indices):
                                row_index = batch_indices[i]
                                row_position = row_index - 1  # Convert to 0-indexed for data array
                                
                                # Check if we need to extend the row
                                if row_position < len(current_data):
                                    row_data = current_data[row_position]
                                    
                                    # Make sure row has enough cells
                                    while len(row_data) <= max(headline_idx, review_idx):
                                        row_data.append("")
                                    
                                    # Update headline and review in the row data
                                    row_data[headline_idx] = review["headline"]
                                    row_data[review_idx] = review["review"]
                                    
                                    # Add to batch updates
                                    batch_updates.append({
                                        'range': f'A{row_index}:{chr(65 + len(row_data) - 1)}{row_index}',
                                        'values': [row_data]
                                    })
                        
                        # Execute batch update if we have updates to make
                        if batch_updates:
                            self.update_status.emit(f"Executing batch update for {len(batch_updates)} rows...")
                            leads_sheet.batch_update(batch_updates)
                            self.update_status.emit(f"Batch update completed successfully.")
                        
                        self.update_status.emit(f"✅ Batch {start+1}-{end} processed and saved.")
                    
                    except json.JSONDecodeError as json_err:
                        self.update_status.emit(f"❌ Error parsing JSON response: {str(json_err)}")
                        self.update_status.emit(f"Raw response: {response_content[:200]}...")  # Show first 200 chars
                        continue
                        
                    # Pause to respect rate limits
                    time.sleep(2)
                    
                except Exception as e:
                    self.update_status.emit(f"❌ Error in batch {start+1}-{end}: {str(e)}")
                    continue
            
            self.update_status.emit(f"🎉 All batches processed and saved.")
            
        except Exception as e:
            self.update_status.emit(f"❌ Error during review writing: {str(e)}") 