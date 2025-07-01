# Amazon Review Bot

A powerful desktop application for automating Amazon review workflows, including scraping, writing, and uploading reviews, as well as forwarding Amazon order emails via Gmail. Built with a modern PyQt5 GUI and integrates with Google Sheets and OpenAI.

---

## Features

- **Gmail Integration**: Automatically processes and forwards Amazon order emails, with date filtering and live status updates.
- **Review Scraper**: Scrapes product data from Google Sheets for review generation.
- **Review Writer**: Uses OpenAI to generate authentic, human-like Amazon reviews and headlines, based on a customizable prompt.
- **Review Uploader**: Uploads generated reviews back to Google Sheets.
- **Modern GUI**: All features are accessible via a user-friendly PyQt5 interface, with real-time feedback and controls.
- **Customizable Prompts**: Easily edit the review writing prompt in a text file (`review_prompt.txt`) without changing code.

---

## Requirements

- Python 3.8+
- Google API credentials for Gmail and Sheets
- OpenAI API key
- Chrome browser (for SeleniumBase)
- The following Python packages:
  - `PyQt5`
  - `openai`
  - `seleniumbase`
  - `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
  - `beautifulsoup4`

Install dependencies with:
```bash
pip install -r requirements.txt
```

---

## Installation & Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd gmailone
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Google API Credentials**
   - Place your Google Sheets credentials as `credentials.json` in the project root.
   - Place your Gmail credentials as `credentials_gmail.json` in the project root.

4. **OpenAI API Key**
   - Obtain your OpenAI API key from https://platform.openai.com/

5. **Prompt File**
   - The review writing prompt is stored in `review_prompt.txt`.
   - Edit this file to customize how reviews are generated.

---

## Usage

### 1. **Start the Application**

```bash
python main.py
```

### 2. **GUI Overview**

- **Review Scraper Tab**: Upload credentials, enter Google Sheet ID (default provided), and start scraping product data.
- **Review Writer Tab**: Upload credentials, enter Google Sheet ID (default provided), OpenAI API key, batch size, and start generating reviews. The prompt is loaded from `review_prompt.txt`.
- **Review Uploader Tab**: Upload credentials, enter Google Sheet ID (default provided), set upload interval, and start uploading reviews.
- **Gmail Integration Tab**: Upload Gmail credentials, set target email, filter by year/month/day, and start/stop Gmail processing. Live status updates are shown.

### 3. **Customizing the Review Prompt**

- Edit `review_prompt.txt` to change the instructions for review generation.
- Use `{PRODUCTS_DATA}` as a placeholder in the prompt; it will be replaced with the product data for each batch.
- No code changes are needed—just save the file and restart the app if running.

### 4. **Google Sheets Format**

Your Google Sheet should have the following columns:
- `Review`
- `Headline`
- `Product_name` or `Product`
- `Asin`
- `Date`

---

## Configuration

- **Default Google Sheet ID**: The app uses `15BLhaWPCci2P6pQReMBcvFWbpTuifYgdgvdcKeQgdIY` by default in all relevant tabs. You can change it in the GUI if needed.
- **Credentials**: Use the GUI to upload your credentials for each module.

---

## Troubleshooting

- If Gmail integration is not available, ensure all dependencies are installed and your credentials are correct.
- For OpenAI errors, check your API key and usage limits.
- For Google Sheets errors, verify your credentials and sheet permissions.

---

## License

MIT License

---

## Credits

- Built with PyQt5, SeleniumBase, OpenAI, and Google APIs.
- Developed by [Your Name/Team]. 