from mcp.server import FastMCP
from mcp.types import TextContent
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import base64
from email.mime.text import MIMEText
import argparse
from models import SendEmailInput, SendEmailOutput

# Initialize the MCP server
mcp = FastMCP("Gmail")
mcp.state = {}  # Initialize the state dictionary

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service(creds_file_path: str, token_path: str):
    """Get Gmail service instance"""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_file_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    try:
        # Call the Gmail API
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f'An error occurred: {e}')
        return None

@mcp.tool()
def send_email(input: SendEmailInput) -> SendEmailOutput:
    """Send an email using Gmail API"""
    try:
        service = mcp.state.get('gmail_service')
        if not service:
            raise ValueError("Gmail service not initialized")

        # Create message
        message = MIMEText(input.message)
        message['to'] = input.to
        message['subject'] = input.subject

        # Encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Send the email
        send_message = (service.users().messages().send(
            userId="me",
            body={'raw': encoded_message})
        ).execute()

        print(f"Email sent successfully. Message Id: {send_message['id']}")

        # Return the output model directly
        return SendEmailOutput(
            message_id=send_message['id'],
            email_sent=True
        )

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise ValueError(f"Failed to send email: {str(e)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--creds-file-path', required=True, help='Path to credentials.json')
    parser.add_argument('--token-path', required=True, help='Path to token.json')
    args = parser.parse_args()

    # Initialize Gmail service
    service = get_gmail_service(args.creds_file_path, args.token_path)
    if service:
        mcp.state['gmail_service'] = service
        print("Gmail service initialized successfully")
    else:
        print("Failed to initialize Gmail service")

    # Run with explicit stdio transport
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main() 