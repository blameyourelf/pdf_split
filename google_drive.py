import os
import io
import json
import pickle
import tempfile
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not found, using environment variables directly")

# Directory to cache PDF files locally
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'pdf_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Time to keep cached files (24 hours)
CACHE_DURATION = timedelta(hours=24)

class GoogleDriveManager:
    """Google Drive integration for managing PDF files."""
    
    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')
        self.folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
        self.drive_service = None
        
        # Check multiple locations for the token file
        self.possible_token_paths = [
            os.path.join(CACHE_DIR, 'token.pickle'),  # Default temp location
            '/tmp/pdf_cache/token.pickle',  # Explicit Render location
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token.pickle')  # Project root
        ]
        
        # Verify required environment variables
        self._check_environment()

    def _check_environment(self):
        """Verify all required environment variables are set."""
        missing = []
        for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_DRIVE_FOLDER_ID']:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            print(f"WARNING: Missing required environment variables: {', '.join(missing)}")
            print("Google Drive integration may not function correctly.")
    
    def _find_token_file(self):
        """Find the token file in any of the possible locations."""
        for path in self.possible_token_paths:
            if os.path.exists(path):
                print(f"Found token file at: {path}")
                return path
        
        print(f"No token file found. Searched in: {', '.join(self.possible_token_paths)}")
        return None

    def _get_credentials(self):
        """Get valid credentials from token file or authorize."""
        creds = None
        
        # Find token file
        token_path = self._find_token_file()
        if token_path:
            try:
                with open(token_path, 'rb') as token:
                    # Try different ways to decode the token
                    try:
                        print(f"Loading token from {token_path} (standard way)")
                        creds = pickle.load(token)
                    except Exception as e1:
                        print(f"Error loading token (standard way): {str(e1)}")
                        try:
                            # Reset file pointer
                            token.seek(0)
                            # Try direct Credentials creation
                            print("Trying to create credentials directly from token data")
                            token_data = json.load(token)
                            creds = Credentials.from_authorized_user_info(token_data)
                        except Exception as e2:
                            print(f"Error creating credentials directly: {str(e2)}")
                            raise ValueError("Could not load credentials from token file")
                
                print(f"Successfully loaded credentials from {token_path}")
                print(f"Credential type: {type(creds)}")
                print(f"Token valid: {creds.valid if creds else 'N/A'}")
                print(f"Token expired: {creds.expired if creds else 'N/A'}")
                print(f"Has refresh token: {'Yes' if creds and creds.refresh_token else 'No'}")
            except Exception as e:
                print(f"Error loading credentials from {token_path}: {str(e)}")
                # Try generating a readable version of the file to debug
                try:
                    with open(token_path, 'rb') as f:
                        data = f.read()
                    print(f"Token file size: {len(data)} bytes")
                    print(f"First few bytes: {data[:20]}")
                except Exception as e:
                    print(f"Could not read token file: {str(e)}")
        else:
            print("No token file found in any of the expected locations")
        
        # If no valid credentials, let's create the flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed credentials
                    self._save_credentials(creds)
                except Exception as e:
                    print(f"Error refreshing token: {str(e)}")
                    creds = None
            else:
                # Create OAuth flow from environment variables
                client_config = self._create_client_config()
                
                # For server environment, this won't work without a browser
                print("Authorization needed. Please generate token using auth_drive.py first.")
                return None
                
        return creds

    def _create_client_config(self):
        """Create OAuth client config from environment variables."""
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')
        
        if not client_id or not client_secret:
            print("Missing OAuth credentials - check environment variables")
            return None
        
        # Try both web and installed app formats
        configs = [
            {
                'web': {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uris': [redirect_uri, 'http://localhost:8080'],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }
            },
            {
                'installed': {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uris': [redirect_uri, 'http://localhost:8080'],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }
            }
        ]
        
        return configs
    
    def _save_credentials(self, creds):
        """Save credentials to all possible locations."""
        for path in self.possible_token_paths:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                with open(path, 'wb') as token:
                    pickle.dump(creds, token)
                print(f"Saved credentials to {path}")
            except Exception as e:
                print(f"Error saving credentials to {path}: {str(e)}")

    def initialize_service(self):
        """Initialize the Drive API service."""
        try:
            creds = self._get_credentials()
            if not creds:
                print("No valid credentials available. Run auth_drive.py first.")
                return False
                
            self.drive_service = build('drive', 'v3', credentials=creds)
            print("Google Drive service initialized successfully")
            return True
        except Exception as e:
            print(f"Error initializing Google Drive service: {str(e)}")
            return False
    
    def list_pdf_files(self):
        """List all PDF files in the specified folder."""
        if not self.drive_service:
            if not self.initialize_service():
                return []
        
        try:
            query = f"'{self.folder_id}' in parents and mimeType='application/pdf' and trashed=false"
            response = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, modifiedTime)'
            ).execute()
            
            files = response.get('files', [])
            print(f"Found {len(files)} PDF files in Google Drive folder")
            return files
        except Exception as e:
            print(f"Error listing PDF files: {str(e)}")
            return []
    
    def get_file_info(self, file_id):
        """Get metadata for a specific file."""
        if not self.drive_service:
            if not self.initialize_service():
                return None
        
        try:
            return self.drive_service.files().get(fileId=file_id).execute()
        except Exception as e:
            print(f"Error getting file info: {str(e)}")
            return None
    
    def get_local_path(self, file_id, filename):
        """Get path to cached file or download if not cached."""
        cached_path = os.path.join(CACHE_DIR, f"{file_id}_{filename}")
        
        # Check if file exists in cache and is recent enough
        if os.path.exists(cached_path):
            file_time = datetime.fromtimestamp(os.path.getmtime(cached_path))
            if datetime.now() - file_time < CACHE_DURATION:
                return cached_path
        
        # Download file if not in cache or too old
        if not self.drive_service:
            if not self.initialize_service():
                return None
        
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            print(f"Downloading {filename} from Google Drive...")
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%")
            
            # Save to cache
            with open(cached_path, 'wb') as f:
                f.write(file_content.getvalue())
            
            print(f"File cached at {cached_path}")
            return cached_path
        except Exception as e:
            print(f"Error downloading file {filename}: {str(e)}")
            return None
    
    def get_ward_metadata(self):
        """Get metadata for all ward PDF files."""
        import re
        wards_meta = {}
        
        # First check if we can initialize the service
        if not self.drive_service and not self.initialize_service():
            print("Failed to initialize Google Drive service")
            return {}
        
        print("Fetching files from Google Drive folder...")
        files = self.list_pdf_files()
        
        if not files:
            print("No PDF files found in Google Drive folder")
            print(f"Folder ID: {self.folder_id}")
            return {}
        
        print(f"Found {len(files)} PDF files in Google Drive")    
        for file in files:
            filename = file['name']
            print(f"Processing file: {filename}")
            if filename.startswith('ward_') and filename.endswith('_records.pdf'):
                # Extract ward name/number between 'ward_' and '_records.pdf'
                ward_part = filename[5:-12]  # Remove 'ward_' and '_records.pdf'
                
                print(f"Extracted ward part: {ward_part}")
                
                # For numbered wards that use Long_X format
                if ward_part.startswith('Long_'):
                    display_name = f"Long {ward_part[5:]}"  # Convert Long_1 to "Long 1"
                # For numeric ward names, prepend "Ward"
                elif ward_part.isdigit():
                    display_name = f"Ward {ward_part}"
                else:
                    display_name = ward_part  # Keep special ward names as is
                
                wards_meta[ward_part] = {
                    "filename": filename,
                    "file_id": file['id'],
                    "display_name": display_name,
                    "patients": {}  # Empty placeholder, will be filled on demand
                }
                print(f"Added ward: {ward_part} -> {display_name}")
        
        if not wards_meta:
            print("No ward PDF files found in Google Drive folder")
            
        # Sort wards
        sorted_ward_nums = sorted(wards_meta.keys(), key=lambda x: wards_meta[x]["display_name"].lower())
        sorted_wards_meta = {}
        for ward_num in sorted_ward_nums:
            sorted_wards_meta[ward_num] = wards_meta[ward_num]
        
        return sorted_wards_meta
