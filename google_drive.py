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
        self.token_path = os.path.join(CACHE_DIR, 'token.pickle')
        
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
    
    def _get_credentials(self):
        """Get valid credentials from token file or authorize."""
        creds = None
        
        # Check if we have a saved token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, let's create the flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {str(e)}")
                    creds = None
            else:
                # Create OAuth flow from environment variables
                client_config = {
                    'web': {
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'redirect_uris': [self.redirect_uri, 'http://localhost:8080'],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                    }
                }
                
                # For server environment, this won't work without a browser
                print("Authorization needed. Please generate token using auth_drive.py first.")
                return None
                
            # Save the refreshed or new credentials
            if creds:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
                
        return creds
    
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
        files = self.list_pdf_files()
        
        if not files:
            print("No PDF files found in Google Drive folder")
            return {}
            
        for file in files:
            filename = file['name']
            if filename.startswith('ward_') and filename.endswith('_records.pdf'):
                # Extract ward name/number between 'ward_' and '_records.pdf'
                ward_part = filename[5:-12]  # Remove 'ward_' and '_records.pdf'
                
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
                print(f"Found ward: {display_name} ({filename})")
        
        # Sort wards
        sorted_ward_nums = sorted(wards_meta.keys(), key=lambda x: wards_meta[x]["display_name"].lower())
        sorted_wards_meta = {}
        for ward_num in sorted_ward_nums:
            sorted_wards_meta[ward_num] = wards_meta[ward_num]
        
        return sorted_wards_meta
