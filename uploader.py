import os
import time
import random
import re
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from seleniumbase import SB
from utils import CHROME_DATA_PATH, setup_google_sheets, upload_review

class ReviewUploader(QThread):
    update_status = pyqtSignal(str)
    show_login_dialog = pyqtSignal()
    
    def __init__(self, credentials_file, sheet_id, delay, headless):
        super().__init__()
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.delay = float(delay)
        self.headless = headless
        self.first_run = True
        self.login_confirmed = False
        
    def run(self):
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')
        
        leads_sheet, processed_sheet, not_processed_sheet = setup_google_sheets(
            self.credentials_file, 
            self.sheet_id,
            self.update_status.emit
        )
        
        if not leads_sheet or not processed_sheet or not not_processed_sheet:
            self.update_status.emit("Failed to set up one or more required sheets. Exiting.")
            return
            
        while True:
            try:
                # Get all records including empty rows
                all_values = leads_sheet.get_all_values()
                if not all_values:
                    self.update_status.emit("Empty sheet. Waiting...")
                    time.sleep(self.delay)
                    continue
                    
                # Clean headers by removing trailing/leading spaces
                headers = [h.strip() for h in all_values[0]]
                
                if len(all_values) <= 1:  # Only headers or empty sheet
                    self.update_status.emit("No new leads to process. Waiting...")
                    time.sleep(self.delay)
                    continue
                    
                # Find indices of required columns
                try:
                    review_link_index = headers.index("Review link")
                    review_index = headers.index("Review")
                    headline_index = headers.index("Headline")
                except ValueError as e:
                    self.update_status.emit(f"Required column not found: {str(e)}")
                    time.sleep(self.delay)
                    continue
                    
                with SB(uc=True, headless=self.headless, locale_code="en", do_not_track=True, user_data_dir=CHROME_DATA_PATH) as sb:
                    # Process each row starting from index 1 (after headers)
                    if self.first_run:
                        sb.open("http://vine.amazon.com")
                        self.update_status.emit("Please log in to Amazon Vine in the browser window...")
                        
                        # Emit signal to show login dialog in main thread
                        self.show_login_dialog.emit()
                        
                        # Wait for login confirmation
                        while not self.login_confirmed:
                            time.sleep(1)
                            
                        self.first_run = False
                        self.login_confirmed = False  # Reset for next time
                        
                    # Look for rows with non-empty reviews and headlines
                    rows_to_process = []
                    for row_idx in range(1, len(all_values)):
                        row = all_values[row_idx]
                        
                        # Check if Review link exists
                        has_review_link = (review_link_index < len(row) and row[review_link_index].strip())
                        
                        # Check if both Review and Headline are filled
                        has_review = (review_index < len(row) and row[review_index].strip())
                        has_headline = (headline_index < len(row) and row[headline_index].strip())
                        
                        if has_review_link and has_review and has_headline:
                            rows_to_process.append((row_idx, row))
                    
                    if not rows_to_process:
                        self.update_status.emit("No rows with complete reviews and headlines to process. Waiting...")
                        time.sleep(self.delay)
                        continue
                        
                    self.update_status.emit(f"Found {len(rows_to_process)} rows with complete reviews and headlines to process")
                        
                    # Process rows in reverse order to avoid index issues when deleting
                    for row_idx, row in sorted(rows_to_process, key=lambda x: x[0], reverse=True):
                        # Convert row to dictionary using cleaned headers
                        data = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
                        
                        self.update_status.emit(f"Processing lead {row_idx+1}")
                        
                        try:
                            website = data.get("Review link", "").strip()
                            self.update_status.emit(f"Opening website: {website}")
                            
                            # Clean data before processing
                            cleaned_data = {k: str(v).strip() for k, v in data.items()}
                            
                            # Extract ASIN from URL if not provided
                            if not cleaned_data.get("Asin") or cleaned_data.get("Asin") == "":
                                try:
                                    # Extract ASIN from URL format: asin=XXXXXXXXXX
                                    asin_match = re.search(r'asin=([A-Z0-9]+)', website)
                                    if asin_match:
                                        extracted_asin = asin_match.group(1)
                                        cleaned_data["Asin"] = extracted_asin
                                        self.update_status.emit(f"Extracted ASIN: {extracted_asin}")
                                except Exception as e:
                                    self.update_status.emit(f"Failed to extract ASIN: {str(e)}")
                            
                            # Open the review page
                            sb.open(website)
                            time.sleep(random.uniform(2, 4))
                            
                            success = upload_review(sb, cleaned_data)
                            
                            if success:
                                # Update status to "Reviewed"
                                cleaned_data["Status"] = "Reviewed"
                                
                                # Take screenshot
                                asin = cleaned_data.get("Asin", "unknown")
                                safe_filename = "".join(c for c in asin if c.isalnum())
                                screenshot_path = os.path.join('screenshots', f"{safe_filename}.png")
                                sb.save_screenshot(screenshot_path)
                                
                                # Save to processed sheet
                                row_data = [cleaned_data.get(col, "") for col in headers]
                                processed_sheet.append_row(row_data)
                                
                                # Delete from leads sheet
                                leads_sheet.delete_rows(row_idx + 1)
                                
                                self.update_status.emit(f"Successfully processed lead {row_idx+1}")
                            else:
                                raise Exception("Failed to upload review")
                            
                            # Wait between processing reviews
                            time.sleep(random.uniform(self.delay*0.7, self.delay*1.4))
                            
                        except Exception as e:
                            error_message = str(e)
                            self.update_status.emit(f"Error processing lead {row_idx+1}: {error_message}")
                            
                            # Save to not_processed sheet with error message
                            row_data = [data.get(col, "") for col in headers]
                            row_data.append(error_message)
                            not_processed_sheet.append_row(row_data)
                            
                            # Delete from leads sheet
                            leads_sheet.delete_rows(row_idx + 1)
                            continue
                            
                    time.sleep(self.delay)
                
            except Exception as e:
                self.update_status.emit(f"Main process error: {str(e)}")
                time.sleep(self.delay)
                continue
                
    def confirm_login(self):
        """Called by the main thread when login is confirmed"""
        self.login_confirmed = True 