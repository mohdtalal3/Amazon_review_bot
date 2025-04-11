from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QFileDialog, QLineEdit, QLabel, QTextEdit, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
import time
import os
import sys
import gspread
from google.oauth2.service_account import Credentials
from seleniumbase import SB
from utils import *
import re

full_path = os.path.abspath("chromedata1")
class LeadProcessor(QThread):
    update_status = pyqtSignal(str)
    
    def __init__(self, credentials_file, sheet_id, delay, headless):
        super().__init__()
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.count = 0
        self.delay = float(delay)
        self.headless = headless
        self.first_run = True
    def setup_google_sheets(self):
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        try:
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.sheet_id)
            
            # Get or create the sheets
            try:
                leads_sheet = spreadsheet.worksheet("leads")
            except gspread.exceptions.WorksheetNotFound:
                self.update_status.emit("Leads sheet not found!")
                return None, None, None
                
            # Get headers from leads sheet
            headers = leads_sheet.row_values(1)
            if not headers:
                self.update_status.emit("No headers found in leads sheet!")
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
                self.update_status.emit("Creating processed sheet...")
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
                self.update_status.emit("Creating not_processed sheet...")
                not_processed_sheet = spreadsheet.add_worksheet(title="not_processed", rows=1000, cols=len(headers_with_error))
                not_processed_sheet.update('A1', [headers_with_error])
                
            return leads_sheet, processed_sheet, not_processed_sheet
            
        except Exception as e:
            self.update_status.emit(f"Error setting up Google Sheets: {str(e)}")
            print(f"Error setting up Google Sheets: {str(e)}")
            return None, None, None

    def run(self):
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')
        self.process_leads()

    def process_leads(self):
        leads_sheet, processed_sheet, not_processed_sheet = self.setup_google_sheets()
        if not leads_sheet or not processed_sheet or not not_processed_sheet:
            self.update_status.emit("Failed to set up one or more required sheets. Exiting.")
            return
            
        while True:
            try:
                # Get all records including empty rows
                all_values = leads_sheet.get_all_values()
                if not all_values:
                    self.update_status.emit("Empty sheet. Waiting...")
                    print("Empty sheet. Waiting...")
                    time.sleep(self.delay)
                    continue
                    
                # Clean headers by removing trailing/leading spaces
                headers = [h.strip() for h in all_values[0]]
                
                if len(all_values) <= 1:  # Only headers or empty sheet
                    self.update_status.emit("No new leads to process. Waiting...")
                    print("No new leads to process. Waiting...")
                    time.sleep(self.delay)
                    continue
                    
                # Find index of Review link column
                try:
                    review_link_index = headers.index("Review link")
                except ValueError:
                    self.update_status.emit("Review link column not found in headers!")
                    print("Review link column not found in headers!")
                    return
                with SB(uc=True, headless=self.headless, locale_code="en", do_not_track=True,user_data_dir=full_path) as sb:
                    # Process each row starting from index 1 (after headers)

                    if self.first_run:
                        sb.open("http://vine.amazon.com")
                        input("Press Enter to continue...")
                        self.first_run = False
                    for row_idx in range(len(all_values) - 1, 0, -1):
                        row = all_values[row_idx]
                        
                        # Skip row if Review link is empty
                        if row_idx >= len(row) or review_link_index >= len(row) or not row[review_link_index].strip():
                            print("No review link for this row")
                            continue
                            
                        # Convert row to dictionary using cleaned headers
                        data = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
                        
                        self.update_status.emit(f"Processing lead {row_idx}")
                        print(f"Processing lead {row_idx}")
                        
                        try:
                            website = data.get("Review link", "").strip()
                            self.update_status.emit(f"Opening website: {website}")
                            print(f"Opening website: {website}")
                            
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
                            
                            # Create a new browser instance for each review 
                            
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
                                
                                self.update_status.emit(f"Successfully processed lead {row_idx}")
                                print(f"Successfully processed lead {row_idx}")
                            else:
                                raise Exception("Failed to upload review")
                            
                            # Wait between processing reviews
                            time.sleep(random.uniform(self.delay*0.7, self.delay*1.4))
                            
                        except Exception as e:
                            error_message = str(e)
                            self.update_status.emit(f"Error processing lead {row_idx}: {error_message}")
                            print(f"Error processing lead {row_idx}: {error_message}")
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amazon Review Processor")
        self.setFixedSize(600, 550)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Style sheet
        self.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin: 5px;
            }
            QLabel {
                margin: 5px;
            }
            QCheckBox {
                margin: 5px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
        """)
        
        # UI Elements
        self.credentials_btn = QPushButton("Upload Credentials File")
        self.credentials_label = QLabel("No credentials file selected")
        
        self.sheet_id_label = QLabel("Google Sheet ID:")
        self.sheet_id_input = QLineEdit()
        
        self.delay_label = QLabel("Check Interval (seconds):")
        self.delay_input = QLineEdit()
        self.delay_input.setText("60")  # Default 60 seconds
        
        self.headless_checkbox = QCheckBox("Enable Headless Mode")
        self.headless_checkbox.setChecked(False)  # Default to visible browser
        
        self.start_btn = QPushButton("Start Processing")
        
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        
        # Add widgets to layout
        layout.addWidget(self.credentials_btn)
        layout.addWidget(self.credentials_label)
        layout.addWidget(self.sheet_id_label)
        layout.addWidget(self.sheet_id_input)
        layout.addWidget(self.delay_label)
        layout.addWidget(self.delay_input)
        layout.addWidget(self.headless_checkbox)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.status_area)
        
        # Connect signals
        self.credentials_btn.clicked.connect(self.select_credentials)
        self.start_btn.clicked.connect(self.start_processing)
        
        self.credentials_file = None
        self.processor = None
        
    def select_credentials(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Credentials File", "", 
                                               "JSON Files (*.json)")
        if filename:
            self.credentials_file = filename
            self.credentials_label.setText(os.path.basename(filename))
    
    def update_status(self, message):
        self.status_area.append(message)
            
    def start_processing(self):
        if not self.credentials_file:
            self.update_status("Please select a credentials file first!")
            return
            
        sheet_id = self.sheet_id_input.text()
        delay = self.delay_input.text()
        headless = self.headless_checkbox.isChecked()
        
        if not sheet_id or not delay:
            self.update_status("Please fill in all required fields!")
            return
            
        try:
            delay_value = float(delay)
            if delay_value < 0:
                self.update_status("Delay must be a positive number!")
                return
        except ValueError:
            self.update_status("Delay must be a valid number!")
            return
            
        self.processor = LeadProcessor(self.credentials_file, sheet_id, delay, headless)
        self.processor.update_status.connect(self.update_status)
        self.processor.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())