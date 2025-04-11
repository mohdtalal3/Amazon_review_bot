# Amazon Review Processor

A desktop application for automating Amazon product reviews using data from Google Sheets.

## Features

- Automatically submits Amazon product reviews from Google Sheets data
- Maintains persistent login session for Amazon
- Takes screenshots of submitted reviews
- Tracks successful and failed review submissions
- Uses randomized timing to appear more human-like
- Extracts ASIN numbers from review URLs

## Requirements

- Python 3.7 or higher
- PyQt5
- SeleniumBase
- Google API credentials (JSON file)
- Google Sheets with the proper format

## Installation

1. Clone this repository or download the source code
2. Install the required dependencies (For very first time):

For windows:

```bash
pip install pyqt5 gspread google-auth seleniumbase
```
For Mac:

```bash
pip3 install pyqt5 gspread google-auth seleniumbase
```
3. Create a Google Cloud project and download service account credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Sheets API and Google Drive API
   - Create service account credentials and download as JSON
   - Share your Google Sheet with the email address in the service account JSON

## Google Sheet Format

Your Google Sheet should contain these columns:
- Review (the review text)
- Headline (review title)
- Product (product name) 
- Date
- Status (will be updated to "Reviewed" when processed)
- Review link (Amazon review URL with ASIN)
- Asin (product ASIN, can be empty and will be extracted from the URL)

## Usage

1. Run the application:

For windows:

```bash
python main.py 
```
For Mac:

```bash
python3 main.py
```

2. Click "Upload Credentials File" to select your Google API credentials JSON file
3. Enter your Google Sheet ID (from the URL of your sheet)
4. Set check interval (how often to check for new reviews)
5. Click "Manual Login" to log in to Amazon (required first time)
6. Click "Start Processing" to begin processing reviews

The first time you run the application, you'll be prompted to manually log in to Amazon. The session will be saved for future use.

## How it Works

1. The app connects to your Google Sheet and reads the "leads" worksheet
2. For each row with a review link, it:
   - Opens a browser with the review link
   - Fills in the review details (5-star rating, headline, review text)
   - Submits the review
   - Takes a screenshot
   - Moves the row to the "processed" worksheet
   - Updates the status to "Reviewed"
3. If any errors occur, the row is moved to "not_processed" with error details

## Troubleshooting

- **Login Issues**: Use the "Manual Login" button to log in again if your session expires
- **Captchas**: Amazon may sometimes show captchas. The app will wait for you to solve them
- **Browser Visibility**: Uncheck "Enable Headless Mode" to see the browser and debug issues

## Files

- `main.py`: Main application code
- `utils.py`: Helper functions for review submission
- `chromedata1/`: Directory for storing browser session data
- `screenshots/`: Directory for storing screenshots of submitted reviews

## Notes

- The app uses a persistent Chrome profile to maintain login state
- Review submission has randomized timing to appear more natural
- Screenshots are named using the product ASIN 