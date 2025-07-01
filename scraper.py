import os
import time
import re
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from seleniumbase import SB
from utils import CHROME_DATA_PATH, setup_google_sheets

class ReviewScraper(QThread):
    update_status = pyqtSignal(str)
    show_login_dialog = pyqtSignal()
    
    def __init__(self, credentials_file, sheet_id, headless=False):
        super().__init__()
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.headless = headless
        self.seen_urls = set()
        self.login_confirmed = False
        
    def run(self):
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
            
        # Load existing URLs from Google Sheets to avoid duplicates
        all_values = leads_sheet.get_all_values()
        headers = all_values[0] if all_values else []
        
        try:
            product_idx = headers.index("Product")
            for row in all_values[1:]:
                if product_idx < len(row) and row[product_idx]:
                    self.seen_urls.add(row[product_idx])
            
            self.update_status.emit(f"Loaded {len(self.seen_urls)} existing product URLs to avoid duplicates")
        except (ValueError, IndexError):
            self.update_status.emit("Warning: Could not find Product column in Google Sheet")
        
        try:
            with SB(uc=True, headless=self.headless, user_data_dir=CHROME_DATA_PATH) as sb:
                sb.open("https://www.amazon.com/vine/vine-reviews?page=1&review-type=pending_review")
                self.update_status.emit("🔐 Please log in to Amazon Vine in the browser window...")
                
                # Show login dialog and wait for confirmation
                self.show_login_dialog.emit()
                
                # Wait for login confirmation
                while not self.login_confirmed:
                    time.sleep(1)
                
                self.update_status.emit("Login confirmed. Starting scraping process...")
                
                page_num = 1
                total_new_products = 0
                
                while True:
                    self.update_status.emit(f"Scraping page {page_num}...")
                    rows = sb.driver.find_elements("css selector", "tr.vvp-reviews-table--row")
                    new_rows = []

                    for row in rows:
                        try:
                            product_name = row.find_element("css selector", "span.a-truncate-full.a-offscreen").get_attribute("textContent").strip()
                            product_url = row.find_element("css selector", "a#vvp-reviews-product-detail-page-link").get_attribute("href")
                            order_date = row.find_element("css selector", "td[data-order-timestamp]").text
                            review_status = "Not yet reviewed"
                            review_link = row.find_element("css selector", "a[name='vvp-reviews-table--review-item-btn']").get_attribute("href")

                            # Check if we've already seen this URL
                            if product_url not in self.seen_urls:
                                # Extract ASIN if possible
                                asin = ""
                                try:
                                    asin_match = re.search(r'asin=([A-Z0-9]+)', review_link)
                                    if asin_match:
                                        asin = asin_match.group(1)
                                except Exception:
                                    pass
                                
                                new_row = {
                                    "Review": "",
                                    "Product_name": product_name,
                                    "Headline":"",
                                    "Product": product_url,
                                    "Date": order_date,
                                    "Status": review_status,
                                    "Review link": review_link,
                                    "Asin": asin
                                }
                                
                                new_rows.append(new_row)
                                self.seen_urls.add(product_url)
                                self.update_status.emit(f"Found new product: {product_name}")
                            else:
                                self.update_status.emit(f"Skipping duplicate product: {product_name}")

                        except Exception as e:
                            self.update_status.emit(f"⚠️ Error parsing row: {str(e)}")

                    if new_rows:
                        # Save all rows from this page to Google Sheet at once
                        sheet_rows = []
                        for new_row in new_rows:
                            row_data = [new_row.get(header, "") for header in headers]
                            sheet_rows.append(row_data)
                        
                        # Batch append to Google Sheet
                        leads_sheet.append_rows(sheet_rows)
                        self.update_status.emit(f"✅ Added {len(new_rows)} products to Google Sheet.")
                        total_new_products += len(new_rows)
                    else:
                        self.update_status.emit("No new products found on this page.")

                    # Try to go to the next page
                    try:
                        next_btn = sb.find_elements("//li[contains(@class, 'a-last') and not(contains(@class, 'disabled'))]/a[contains(text(), 'Next')]")
                        if not next_btn:
                            self.update_status.emit(f"✅ No more pages. Scraping completed. Found {total_new_products} new products.")
                            break
                        next_btn[-1].click()
                        page_num += 1
                        time.sleep(3)
                    except Exception as e:
                        self.update_status.emit(f"✅ No more pages or error navigating: {str(e)}")
                        break
                        
        except Exception as e:
            self.update_status.emit(f"❌ Error during scraping: {str(e)}")
            
    def confirm_login(self):
        """Called by the main thread when login is confirmed"""
        self.login_confirmed = True 