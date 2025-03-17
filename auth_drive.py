import os
import pickle
import sys
import tempfile

# Try to import dependencies or install them if missing
try:
    from dotenv import load_dotenv
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    print("Missing packages detected. Installing now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "python-dotenv",
                           "google-api-python-client",
                           "google-auth-httplib2",
                           "google-auth-oauthlib"])
    from dotenv import load_dotenv
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

# Load environment variables from .env
load_dotenv()

# Define the scopes for Google Drive access
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Path to store token
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'pdf_cache')
os.makedirs(CACHE_DIR, exist_ok=True)
TOKEN_PATH = os.path.join(CACHE_DIR, 'token.pickle')

def authenticate():
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.")
        sys.exit(1)

    creds = None

    # Check if token already exists
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    # Refresh token if expired and refresh token is available
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("Token refreshed successfully.")
        except Exception as e:
            print(f"Error refreshing token: {e}")
            creds = None

    # If credentials are not valid or no token exists, start authentication flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["http://localhost:8080"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            SCOPES
        )

        creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')

        # Save credentials to token file
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
        print(f"Authentication complete. Token saved to {TOKEN_PATH}.")

if __name__ == '__main__':
    authenticate()