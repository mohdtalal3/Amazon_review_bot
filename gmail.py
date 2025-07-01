import os
import base64
import mimetypes
import urllib.parse
import re
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from seleniumbase import SB
import time
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime

CHROME_DATA_PATH = os.path.abspath("chromedata1")

def open_link(sb, url):
    try:
        sb.open(url)
        time.sleep(2)
        sb.wait_for_element('//a[contains(text(), "View order")]', timeout=10)
        link = sb.get_attribute('//a[contains(text(), "View order")]', 'href')
        order_id = link.split("orderID=")[-1]
        return order_id
    except Exception as e:
        return False

# --- Config ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
MAX_EMAILS = 1
AMAZON_LABEL_ID = 'Label_3944280798531527120'  # Replace with your actual Gmail label ID

class GmailProcessor(QThread):
    update_status = pyqtSignal(str)
    
    def __init__(self, credentials_file, target_email, year=None, month=None, day=None):
        super().__init__()
        self.credentials_file = credentials_file
        self.target_email = target_email
        self.year = year
        self.month = month
        self.day = day
        self.running = True
        
    def run(self):
        try:
            self.update_status.emit("🔐 Authenticating Gmail...")
            gmail_service = self.authenticate_gmail()
            
            self.update_status.emit("🌐 Starting Chrome browser...")
            with SB(uc=True, user_data_dir=CHROME_DATA_PATH) as sb:
                self.fetch_unread_emails(gmail_service, sb)
                
        except Exception as e:
            self.update_status.emit(f"❌ Error: {str(e)}")
    
    def stop(self):
        self.running = False
        
    def authenticate_gmail(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)

    def get_body(self, payload):
        html_body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    html_body = base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore')
                    break
            if not html_body:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        return base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore'), ""
        else:
            if payload['mimeType'] == 'text/html':
                html_body = base64.urlsafe_b64decode(payload['body'].get('data', '')).decode('utf-8', errors='ignore')
            elif payload['mimeType'] == 'text/plain':
                return base64.urlsafe_b64decode(payload['body'].get('data', '')).decode('utf-8', errors='ignore'), ""
        return "", html_body

    def extract_amazon_product_urls(self, html_body):
        soup = BeautifulSoup(html_body, "html.parser")
        links = soup.find_all("a", href=True)
        product_urls = []

        for link in links:
            href = link['href']
            parsed = urllib.parse.urlparse(href)
            query_params = urllib.parse.parse_qs(parsed.query)

            # Get real target from 'U' parameter
            if 'U' in query_params:
                real_url = urllib.parse.unquote(query_params['U'][0])
                if re.match(r'^https:\/\/www\.amazon\.com\/dp\/[A-Z0-9]{10}\/ref=', real_url):
                    product_urls.append(real_url)

        return product_urls

    def forward_email_as_is_with_new_subject(self, service, message_id, order_id, to_email):
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        # Extract original content
        plain_body, html_body = self.get_body(payload)
        content = html_body if html_body else plain_body

        # Create new message
        new_msg = EmailMessage()
        new_msg['To'] = to_email
        new_msg['Subject'] = order_id
        new_msg.set_content(content, subtype='html' if html_body else 'plain')

        # Encode and send
        encoded_message = base64.urlsafe_b64encode(new_msg.as_bytes()).decode()
        send_result = service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()

        self.update_status.emit(f"📨 Forwarded email to {to_email} with subject: {order_id}")

    def build_date_query(self):
        """Build date query string based on year, month, day selection"""
        if not self.year:
            return "after:2025/01/01"  # Default to current year
            
        if self.year and self.month and self.day:
            # Specific date
            date_str = f"{self.year}/{self.month:02d}/{self.day:02d}"
            return f"after:{date_str}"
        elif self.year and self.month:
            # Specific month
            date_str = f"{self.year}/{self.month:02d}/01"
            return f"after:{date_str}"
        else:
            # Specific year
            date_str = f"{self.year}/01/01"
            return f"after:{date_str}"

    def fetch_unread_emails(self, service, sb):
        batch_size = 5
        total_processed = 0
        date_query = self.build_date_query()
        
        self.update_status.emit(f"📅 Using date filter: {date_query}")
        
        while self.running:
            try:
                results = service.users().messages().list(
                    userId='me',
                    labelIds=[AMAZON_LABEL_ID, 'UNREAD'],
                    maxResults=batch_size,
                    q=date_query
                ).execute()

                messages = results.get('messages', [])
                if not messages:
                    self.update_status.emit(f"✅ No more unread emails to process. Total processed: {total_processed}")
                    break

                self.update_status.emit(f"📧 Processing batch of {len(messages)} unread email(s)...")
                total_processed += len(messages)

                for msg in messages:
                    if not self.running:
                        break
                        
                    msg_id = msg['id']
                    message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                    payload = message.get('payload', {})
                    headers = payload.get('headers', [])
                    thread_id = message.get('threadId')

                    subject = sender = cc = ""
                    for header in headers:
                        name = header.get('name', '').lower()
                        if name == 'subject':
                            subject = header.get('value', '')
                        elif name == 'from':
                            sender = header.get('value', '')
                        elif name == 'cc':
                            cc = header.get('value', '')

                    plain_body, html_body = self.get_body(payload)

                    self.update_status.emit(f"\nFrom: {sender}\nSubject: {subject}")
                    if cc:
                        self.update_status.emit(f"CC: {cc}")

                    # Extract and print product URLs
                    if html_body:
                        product_urls = self.extract_amazon_product_urls(html_body)
                        self.update_status.emit("✅ Filtered Amazon Product URLs:")
                        for url in product_urls:
                            self.update_status.emit(url)
                            order_id = open_link(sb, url)
                            if order_id:
                                self.update_status.emit(f"🆔 Order ID: {order_id}")
                                self.forward_email_as_is_with_new_subject(service, msg_id, order_id, self.target_email)
                                service.users().messages().modify(
                                userId='me',
                                id=msg_id,
                                body={'removeLabelIds': ['UNREAD']}
                                ).execute()
                                break
                            else:
                                self.update_status.emit("❌ Order ID not found")
                                service.users().messages().modify(
                                userId='me',
                                id=msg_id,
                                body={'removeLabelIds': ['UNREAD']}
                                ).execute()
                                break

                if self.running:
                    self.update_status.emit("⏳ Waiting 2 seconds before processing next batch...")
                    time.sleep(2)  # Small delay between batches to avoid rate limiting
                    
            except Exception as e:
                self.update_status.emit(f"❌ Error processing emails: {str(e)}")
                break

# --- Legacy function for direct execution ---
def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials_gmail.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# --- Extract the plain and HTML parts from the message payload ---
def get_body(payload):
    html_body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/html':
                html_body = base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore')
                break
        if not html_body:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    return base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore'), ""
    else:
        if payload['mimeType'] == 'text/html':
            html_body = base64.urlsafe_b64decode(payload['body'].get('data', '')).decode('utf-8', errors='ignore')
        elif payload['mimeType'] == 'text/plain':
            return base64.urlsafe_b64decode(payload['body'].get('data', '')).decode('utf-8', errors='ignore'), ""
    return "", html_body

# --- Extract only Amazon product URLs from hrefs ---
def extract_amazon_product_urls(html_body):
    soup = BeautifulSoup(html_body, "html.parser")
    links = soup.find_all("a", href=True)
    product_urls = []

    for link in links:
        href = link['href']
        parsed = urllib.parse.urlparse(href)
        query_params = urllib.parse.parse_qs(parsed.query)

        # Get real target from 'U' parameter
        if 'U' in query_params:
            real_url = urllib.parse.unquote(query_params['U'][0])
            if re.match(r'^https:\/\/www\.amazon\.com\/dp\/[A-Z0-9]{10}\/ref=', real_url):
                product_urls.append(real_url)

    return product_urls

def forward_email_as_is_with_new_subject(service, message_id, order_id, to_email):
    message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    payload = message.get('payload', {})
    headers = payload.get('headers', [])

    # Extract original content
    plain_body, html_body = get_body(payload)
    content = html_body if html_body else plain_body

    # Create new message
    new_msg = EmailMessage()
    new_msg['To'] = to_email
    new_msg['Subject'] = order_id
    new_msg.set_content(content, subtype='html' if html_body else 'plain')

    # Encode and send
    encoded_message = base64.urlsafe_b64encode(new_msg.as_bytes()).decode()
    send_result = service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()

    print(f"📨 Forwarded email to {to_email} with subject: {order_id}")

# --- Main Email Processor ---
def fetch_unread_emails(service, sb):
    batch_size = 5
    total_processed = 0
    
    while True:
        results = service.users().messages().list(
            userId='me',
            labelIds=[AMAZON_LABEL_ID, 'UNREAD'],
            maxResults=batch_size,
            q="after:2025/01/01"
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            print(f"\n✅ No more unread emails to process. Total processed: {total_processed}")
            break

        print(f"\n📧 Processing batch of {len(messages)} unread email(s)...")
        total_processed += len(messages)

        for msg in messages:
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            thread_id = message.get('threadId')

            subject = sender = cc = ""
            for header in headers:
                name = header.get('name', '').lower()
                if name == 'subject':
                    subject = header.get('value', '')
                elif name == 'from':
                    sender = header.get('value', '')
                elif name == 'cc':
                    cc = header.get('value', '')

            plain_body, html_body = get_body(payload)

            print(f"\nFrom: {sender}\nSubject: {subject}")
            if cc:
                print(f"CC: {cc}")

            # Extract and print product URLs
            if html_body:
                product_urls = extract_amazon_product_urls(html_body)
                print("✅ Filtered Amazon Product URLs:")
                for url in product_urls:
                    print(url)
                    order_id = open_link(sb, url)
                    if order_id:
                        print(f"🆔 Order ID: {order_id}")
                        forward_email_as_is_with_new_subject(service, msg_id, order_id, "unacary33@gmail.com")
                        service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        break
                    else:
                        print("❌ Order ID not found")
                        service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        break

        print(f"\n⏳ Waiting 2 seconds before processing next batch...")
        time.sleep(2)  # Small delay between batches to avoid rate limiting

# --- Run the Script ---
if __name__ == '__main__':
    gmail_service = authenticate_gmail()
    with SB(uc=True, user_data_dir=CHROME_DATA_PATH) as sb:
        fetch_unread_emails(gmail_service, sb)
#u#nacary33@gmail.com