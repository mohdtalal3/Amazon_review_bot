import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QFileDialog, QLineEdit, QLabel, QTextEdit, QCheckBox,
                           QTabWidget, QHBoxLayout, QGroupBox, QFormLayout, QSpinBox,
                           QDoubleSpinBox, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from datetime import datetime

# Import our modules
from scraper import ReviewScraper
from writer import ReviewWriter
from uploader import ReviewUploader

# Try to import Gmail processor (might not be available if dependencies are missing)
try:
    from gmail import GmailProcessor
    GMAIL_AVAILABLE = True
except ImportError as e:
    print(f"Gmail integration not available: {e}")
    GMAIL_AVAILABLE = False
    GmailProcessor = None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amazon Review Bot")
        self.setMinimumSize(800, 600)
        
        # Set up the main tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create tabs
        self.scraper_tab = QWidget()
        self.writer_tab = QWidget()
        self.uploader_tab = QWidget()
        self.gmail_tab = QWidget()  # New Gmail tab
        
        self.tabs.addTab(self.scraper_tab, "Review Scraper")
        self.tabs.addTab(self.writer_tab, "Review Writer")
        self.tabs.addTab(self.uploader_tab, "Review Uploader")
        self.tabs.addTab(self.gmail_tab, "Gmail Integration")  # Add Gmail tab
        
        # Set up each tab
        self.setup_scraper_tab()
        self.setup_writer_tab()
        self.setup_uploader_tab()
        self.setup_gmail_tab()  # Setup Gmail tab
        
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
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
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
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        # Initialize variables
        self.scraper = None
        self.writer = None
        self.uploader = None
        self.gmail_processor = None
        self.credentials_file = None
        
    def closeEvent(self, event):
        """Handle application closing - stop all running threads"""
        if self.gmail_processor and self.gmail_processor.isRunning():
            self.gmail_processor.stop()
            self.gmail_processor.wait(3000)  # Wait up to 3 seconds
        event.accept()
        
    def setup_scraper_tab(self):
        layout = QVBoxLayout()
        self.scraper_tab.setLayout(layout)
        
        # Controls
        controls_group = QGroupBox("Scraper Controls")
        controls_layout = QFormLayout()
        
        self.scraper_credentials_btn = QPushButton("Upload Credentials File")
        self.scraper_credentials_btn.clicked.connect(self.select_scraper_credentials)
        self.scraper_credentials_label = QLabel("No credentials file selected")
        controls_layout.addRow(self.scraper_credentials_btn, self.scraper_credentials_label)
        
        self.scraper_sheet_id_input = QLineEdit()
        self.scraper_sheet_id_input.setText("15BLhaWPCci2P6pQReMBcvFWbpTuifYgdgvdcKeQgdIY")  # Default Sheet ID
        controls_layout.addRow("Google Sheet ID:", self.scraper_sheet_id_input)
        
        self.scraper_headless_checkbox = QCheckBox("Run in Headless Mode")
        controls_layout.addRow(self.scraper_headless_checkbox)
        
        self.start_scraper_btn = QPushButton("Start Scraping")
        self.start_scraper_btn.clicked.connect(self.start_scraping)
        controls_layout.addRow(self.start_scraper_btn)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Status area
        self.scraper_status = QTextEdit()
        self.scraper_status.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.scraper_status)
        
    def setup_writer_tab(self):
        layout = QVBoxLayout()
        self.writer_tab.setLayout(layout)
        
        # Controls
        controls_group = QGroupBox("Writer Controls")
        controls_layout = QFormLayout()
        
        self.writer_credentials_btn = QPushButton("Upload Credentials File")
        self.writer_credentials_btn.clicked.connect(self.select_writer_credentials)
        self.writer_credentials_label = QLabel("No credentials file selected")
        controls_layout.addRow(self.writer_credentials_btn, self.writer_credentials_label)
        
        self.writer_sheet_id_input = QLineEdit()
        self.writer_sheet_id_input.setText("15BLhaWPCci2P6pQReMBcvFWbpTuifYgdgvdcKeQgdIY")  # Default Sheet ID
        controls_layout.addRow("Google Sheet ID:", self.writer_sheet_id_input)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText("")
        controls_layout.addRow("OpenAI API Key:", self.api_key_input)
        
        self.batch_size_input = QSpinBox()
        self.batch_size_input.setMinimum(1)
        self.batch_size_input.setMaximum(50)
        self.batch_size_input.setValue(10)
        controls_layout.addRow("Batch Size:", self.batch_size_input)
        
        self.start_writer_btn = QPushButton("Start Writing Reviews")
        self.start_writer_btn.clicked.connect(self.start_writing)
        controls_layout.addRow(self.start_writer_btn)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Status area
        self.writer_status = QTextEdit()
        self.writer_status.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.writer_status)
        
    def setup_uploader_tab(self):
        layout = QVBoxLayout()
        self.uploader_tab.setLayout(layout)
        
        # Controls
        controls_group = QGroupBox("Uploader Controls")
        controls_layout = QFormLayout()
        
        self.uploader_credentials_btn = QPushButton("Upload Credentials File")
        self.uploader_credentials_btn.clicked.connect(self.select_uploader_credentials)
        self.uploader_credentials_label = QLabel("No credentials file selected")
        controls_layout.addRow(self.uploader_credentials_btn, self.uploader_credentials_label)
        
        self.uploader_sheet_id_input = QLineEdit()
        self.uploader_sheet_id_input.setText("15BLhaWPCci2P6pQReMBcvFWbpTuifYgdgvdcKeQgdIY")  # Default Sheet ID
        controls_layout.addRow("Google Sheet ID:", self.uploader_sheet_id_input)
        
        self.delay_input = QDoubleSpinBox()
        self.delay_input.setMinimum(1)
        self.delay_input.setMaximum(300)
        self.delay_input.setValue(60)
        controls_layout.addRow("Check Interval (seconds):", self.delay_input)
        
        self.uploader_headless_checkbox = QCheckBox("Run in Headless Mode")
        controls_layout.addRow(self.uploader_headless_checkbox)
        
        self.start_uploader_btn = QPushButton("Start Uploading Reviews")
        self.start_uploader_btn.clicked.connect(self.start_uploading)
        controls_layout.addRow(self.start_uploader_btn)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Status area
        self.uploader_status = QTextEdit()
        self.uploader_status.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.uploader_status)
        
    def setup_gmail_tab(self):
        layout = QVBoxLayout()
        self.gmail_tab.setLayout(layout)
        
        # Show warning if Gmail is not available
        if not GMAIL_AVAILABLE:
            warning_label = QLabel("⚠️ Gmail integration is not available. Please install required dependencies.")
            warning_label.setStyleSheet("QLabel { color: red; font-weight: bold; margin: 10px; }")
            layout.addWidget(warning_label)
        
        # Controls
        controls_group = QGroupBox("Gmail Integration Controls")
        controls_layout = QFormLayout()
        
        self.gmail_credentials_btn = QPushButton("Upload Gmail Credentials File")
        self.gmail_credentials_btn.clicked.connect(self.select_gmail_credentials)
        self.gmail_credentials_label = QLabel("No credentials file selected")
        controls_layout.addRow(self.gmail_credentials_btn, self.gmail_credentials_label)
        
        # Target email input
        self.target_email_input = QLineEdit()
        self.target_email_input.setText("unacary33@gmail.com")  # Default email
        self.target_email_input.setPlaceholderText("Enter target email address")
        controls_layout.addRow("Target Email:", self.target_email_input)
        
        # Date filtering controls
        date_group = QGroupBox("Date Filtering")
        date_layout = QFormLayout()
        
        # Year selector
        self.year_combo = QComboBox()
        self.year_combo.addItem("Any Year", None)
        current_year = datetime.now().year
        for year in range(current_year, current_year - 5, -1):  # Last 5 years
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentIndex(1)  # Default to current year
        date_layout.addRow("Year:", self.year_combo)
        
        # Month selector
        self.month_combo = QComboBox()
        self.month_combo.addItem("Any Month", None)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        for i, month in enumerate(months, 1):
            self.month_combo.addItem(month, i)
        date_layout.addRow("Month:", self.month_combo)
        
        # Day selector
        self.day_combo = QComboBox()
        self.day_combo.addItem("Any Day", None)
        for day in range(1, 32):
            self.day_combo.addItem(str(day), day)
        date_layout.addRow("Day:", self.day_combo)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_gmail_btn = QPushButton("Start Gmail Processing")
        self.start_gmail_btn.clicked.connect(self.start_gmail)
        self.stop_gmail_btn = QPushButton("Stop Gmail Processing")
        self.stop_gmail_btn.clicked.connect(self.stop_gmail)
        self.stop_gmail_btn.setEnabled(False)
        self.stop_gmail_btn.setStyleSheet("QPushButton { background-color: #f44336; }")
        
        # Disable controls if Gmail is not available
        if not GMAIL_AVAILABLE:
            self.gmail_credentials_btn.setEnabled(False)
            self.target_email_input.setEnabled(False)
            self.year_combo.setEnabled(False)
            self.month_combo.setEnabled(False)
            self.day_combo.setEnabled(False)
            self.start_gmail_btn.setEnabled(False)
            self.stop_gmail_btn.setEnabled(False)
        
        button_layout.addWidget(self.start_gmail_btn)
        button_layout.addWidget(self.stop_gmail_btn)
        controls_layout.addRow(button_layout)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Status area
        self.gmail_status = QTextEdit()
        self.gmail_status.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.gmail_status)
    
    def select_scraper_credentials(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Credentials File", "", 
                                               "JSON Files (*.json)")
        if filename:
            self.scraper_credentials_file = filename
            self.scraper_credentials_label.setText(os.path.basename(filename))
    
    def select_writer_credentials(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Credentials File", "", 
                                               "JSON Files (*.json)")
        if filename:
            self.writer_credentials_file = filename
            self.writer_credentials_label.setText(os.path.basename(filename))
            
    def select_uploader_credentials(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Credentials File", "", 
                                               "JSON Files (*.json)")
        if filename:
            self.uploader_credentials_file = filename
            self.uploader_credentials_label.setText(os.path.basename(filename))
            
    def select_gmail_credentials(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Gmail Credentials File", "", 
                                               "JSON Files (*.json)")
        if filename:
            self.gmail_credentials_file = filename
            self.gmail_credentials_label.setText(os.path.basename(filename))
            
    def update_scraper_status(self, message):
        self.scraper_status.append(message)
        
    def update_writer_status(self, message):
        self.writer_status.append(message)
        
    def update_uploader_status(self, message):
        self.uploader_status.append(message)
        
    def update_gmail_status(self, message):
        self.gmail_status.append(message)
        
    def show_login_dialog(self, module_name):
        """Show a login dialog and return whether the user confirmed login"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Login Required")
        msg_box.setText(f"Please log in to Amazon Vine in the browser window.\n\nClick OK when you have completed the login.")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
        
        # Return True to indicate user confirmed login
        return True
        
    def start_scraping(self):
        if not hasattr(self, 'scraper_credentials_file'):
            QMessageBox.warning(self, "Warning", "Please select a credentials file first!")
            return
            
        sheet_id = self.scraper_sheet_id_input.text()
        if not sheet_id:
            QMessageBox.warning(self, "Warning", "Please enter a Google Sheet ID!")
            return
            
        headless = self.scraper_headless_checkbox.isChecked()
        
        self.scraper = ReviewScraper(self.scraper_credentials_file, sheet_id, headless)
        self.scraper.update_status.connect(self.update_scraper_status)
        self.scraper.show_login_dialog.connect(lambda: self.handle_login_dialog("scraper"))
        self.scraper.start()
        
        self.update_scraper_status("Starting review scraper...")
        self.start_scraper_btn.setEnabled(False)
        
    def handle_login_dialog(self, module_type):
        """Handle login dialog for different modules"""
        if self.show_login_dialog(module_type):
            if module_type == "scraper" and self.scraper:
                self.scraper.confirm_login()
            elif module_type == "uploader" and self.uploader:
                self.uploader.confirm_login()
        
    def start_writing(self):
        if not hasattr(self, 'writer_credentials_file'):
            QMessageBox.warning(self, "Warning", "Please select a credentials file first!")
            return
            
        sheet_id = self.writer_sheet_id_input.text()
        if not sheet_id:
            QMessageBox.warning(self, "Warning", "Please enter a Google Sheet ID!")
            return
            
        api_key = self.api_key_input.text()
        if not api_key:
            QMessageBox.warning(self, "Warning", "Please enter your OpenAI API key.")
            return
            
        batch_size = self.batch_size_input.value()
        
        self.writer = ReviewWriter(self.writer_credentials_file, sheet_id, api_key, batch_size)
        self.writer.update_status.connect(self.update_writer_status)
        self.writer.start()
        
        self.update_writer_status("Starting review writer...")
        self.start_writer_btn.setEnabled(False)
        
    def start_uploading(self):
        if not hasattr(self, 'uploader_credentials_file'):
            QMessageBox.warning(self, "Warning", "Please select a credentials file first!")
            return
            
        sheet_id = self.uploader_sheet_id_input.text()
        if not sheet_id:
            QMessageBox.warning(self, "Warning", "Please enter a Google Sheet ID!")
            return
            
        delay = self.delay_input.value()
        headless = self.uploader_headless_checkbox.isChecked()
        
        self.uploader = ReviewUploader(self.uploader_credentials_file, sheet_id, delay, headless)
        self.uploader.update_status.connect(self.update_uploader_status)
        self.uploader.show_login_dialog.connect(lambda: self.handle_login_dialog("uploader"))
        self.uploader.start()
        
        self.update_uploader_status("Starting review uploader...")
        self.start_uploader_btn.setEnabled(False)
        
    def start_gmail(self):
        if not GMAIL_AVAILABLE:
            QMessageBox.critical(self, "Error", "Gmail integration is not available. Please check that all required dependencies are installed.")
            return
            
        if not hasattr(self, 'gmail_credentials_file'):
            QMessageBox.warning(self, "Warning", "Please select a Gmail credentials file first!")
            return
            
        target_email = self.target_email_input.text().strip()
        if not target_email:
            QMessageBox.warning(self, "Warning", "Please enter a target email address!")
            return
            
        # Get date filter values
        year = self.year_combo.currentData()
        month = self.month_combo.currentData()
        day = self.day_combo.currentData()
        
        try:
            # Start Gmail processor
            self.gmail_processor = GmailProcessor(
                credentials_file=self.gmail_credentials_file,
                target_email=target_email,
                year=year,
                month=month,
                day=day
            )
            self.gmail_processor.update_status.connect(self.update_gmail_status)
            self.gmail_processor.start()
            
            # Update UI
            self.update_gmail_status("🚀 Starting Gmail integration...")
            self.update_gmail_status(f"📧 Target email: {target_email}")
            if year:
                date_filter = f"Year: {year}"
                if month:
                    date_filter += f", Month: {month}"
                    if day:
                        date_filter += f", Day: {day}"
                self.update_gmail_status(f"📅 Date filter: {date_filter}")
            else:
                self.update_gmail_status("📅 Date filter: Any date")
            
            # Update button states
            self.start_gmail_btn.setEnabled(False)
            self.stop_gmail_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start Gmail processing: {str(e)}")
            
    def stop_gmail(self):
        if self.gmail_processor:
            self.gmail_processor.stop()
            self.gmail_processor.wait()  # Wait for thread to finish
            self.gmail_processor = None
            
            self.update_gmail_status("🛑 Gmail processing stopped by user")
            
            # Update button states
            self.start_gmail_btn.setEnabled(True)
            self.stop_gmail_btn.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 