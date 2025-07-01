import os
import time
import random
import gspread
from google.oauth2.service_account import Credentials

# Global variables
CHROME_DATA_PATH = os.path.abspath("chromedata1")
OUTPUT_FILE = "amazon_reviews.csv"
PROCESSED_FILE = "amazon_vine_reviews.csv"

def setup_google_sheets(credentials_file, sheet_id, update_status_callback=None):
    """
    Set up Google Sheets connection and create necessary worksheets
    
    Args:
        credentials_file: Path to Google service account credentials JSON file
        sheet_id: Google Sheet ID
        update_status_callback: Optional callback function to report status
        
    Returns:
        Tuple of (leads_sheet, processed_sheet, not_processed_sheet) or (None, None, None) on failure
    """
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = Credentials.from_service_account_file(credentials_file, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        
        # Get or create the sheets
        try:
            leads_sheet = spreadsheet.worksheet("leads")
        except gspread.exceptions.WorksheetNotFound:
            if update_status_callback:
                update_status_callback("Leads sheet not found! Creating...")
            leads_sheet = spreadsheet.add_worksheet(title="leads", rows=1000, cols=10)
            # Add default headers for leads sheet
            leads_sheet.update('A1', [["Review", "Product_name", "Headline", "Product", "Date", "Status", "Review link", "Asin"]])
        
        # Get headers from leads sheet
        headers = leads_sheet.row_values(1)
        if not headers:
            if update_status_callback:
                update_status_callback("No headers found in leads sheet!")
            return None, None, None
            
        # Add error column to headers for not_processed sheet
        headers_with_error = headers.copy()
        if "ERROR" not in headers_with_error:
            headers_with_error.append("ERROR")
            
        # Get or create processed sheet
        try:
            processed_sheet = spreadsheet.worksheet("processed")
            # Update headers if needed
            if processed_sheet.row_values(1) != headers:
                processed_sheet.clear()
                processed_sheet.update('A1', [headers])
        except gspread.exceptions.WorksheetNotFound:
            if update_status_callback:
                update_status_callback("Creating processed sheet...")
            processed_sheet = spreadsheet.add_worksheet(title="processed", rows=1000, cols=len(headers))
            processed_sheet.update('A1', [headers])
            
        # Get or create not_processed sheet
        try:
            not_processed_sheet = spreadsheet.worksheet("not_processed")
            # Update headers if needed
            if not_processed_sheet.row_values(1) != headers_with_error:
                not_processed_sheet.clear()
                not_processed_sheet.update('A1', [headers_with_error])
        except gspread.exceptions.WorksheetNotFound:
            if update_status_callback:
                update_status_callback("Creating not_processed sheet...")
            not_processed_sheet = spreadsheet.add_worksheet(title="not_processed", rows=1000, cols=len(headers_with_error))
            not_processed_sheet.update('A1', [headers_with_error])
            
        return leads_sheet, processed_sheet, not_processed_sheet
        
    except Exception as e:
        if update_status_callback:
            update_status_callback(f"Error setting up Google Sheets: {str(e)}")
        print(f"Error setting up Google Sheets: {str(e)}")
        return None, None, None

def upload_review(sb, data):
    """
    Upload a review to Amazon
    
    Args:
        sb: SeleniumBase instance
        data: Dictionary with review data
        
    Returns:
        Boolean indicating success
    """
    try:
        sb.click("img[alt='select to rate item five star.']", timeout=10)
        time.sleep(random.uniform(3, 6))
        sb.click("#reviewText", timeout=10)
        time.sleep(random.uniform(3, 6))   
        sb.type("#reviewText", data["Review"])
        time.sleep(random.uniform(3, 6))
        sb.click("#reviewTitle", timeout=10)
        time.sleep(random.uniform(3, 6))
        sb.type("#reviewTitle", data["Headline"])
        time.sleep(random.uniform(3, 6))
        sb.click('input[type="submit"].a-button-input', timeout=10)
        time.sleep(random.uniform(3, 6))
        return True
    except Exception as e:
        print(e)
        return False

