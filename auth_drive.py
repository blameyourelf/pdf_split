import os
import pickle
import tempfile
import sys

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not found. Installing required packages...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
        from dotenv import load_dotenv
        load_dotenv()
        print("Successfully installed python-dotenv and loaded environment variables.")
    except Exception as e:
        print(f"Failed to install python-dotenv: {e}")
        print("Please manually install required packages with:")
        print("pip install python-dotenv google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        sys.exit(1)

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Cache directory for token
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'pdf_cache')
os.makedirs(CACHE_DIR, exist_ok=True)
TOKEN_PATH = os.path.join(CACHE_DIR, 'token.pickle')

def main():
    """Run the authentication flow to get credentials."""
    # Check for required Google API packages
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("Google API packages not found. Installing required packages...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", 
                                 "google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib"])
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            print("Successfully installed Google API packages.")
        except Exception as e:
            print(f"Failed to install required packages: {e}")
            print("Please manually install required packages with:")
            print("pip install python-dotenv google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            return 1
    
    print("Starting Google Drive authentication...")
    print(f"Token will be saved to: {TOKEN_PATH}")
    
    # Get credentials from environment variables
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')
    
    if not client_id or not client_secret:
        print("Error: Missing Google OAuth credentials in environment variables.")
        print("Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.")
        return 1
    
    creds = None
    
    # Check if token file exists
    if os.path.exists(TOKEN_PATH):
        print(f"Found existing token at {TOKEN_PATH}")
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials don't exist or are invalid, run the flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Token expired, attempting refresh...")
                creds.refresh(Request())
                print("Token refreshed successfully!")
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None
        
        if not creds:
            # Create client config from environment variables
            client_config = {
                'installed': {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uris': [redirect_uri, 'http://localhost:8080'],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }
            }
            
            try:
                print("Starting OAuth authorization flow...")
                # Create flow from client config
                flow = InstalledAppFlow.from_client_config(
                    client_config,
                    SCOPES,
                    redirect_uri='http://localhost:8080'  # Use localhost for local auth
                )
                
                # Run the authorization flow locally
                creds = flow.run_local_server(port=8080)
                print("Authorization successful!")
                
                # Save the credentials for the next run
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
                print(f"Token saved to {TOKEN_PATH}")
                
            except Exception as e:
                print(f"Error during authentication: {e}")
                return 1
    else:
        print("Using existing valid credentials.")
    
    print("Authentication complete and token ready for use.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
