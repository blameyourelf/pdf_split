import os
import io
import json
import pickle
import tempfile
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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

import base64
from googleapiclient.errors import HttpError
import time
import sys

# Fix for circular import issue
sys.modules['googleapiclient.discovery_cache'] = object()
# Now import discovery after the fix
from googleapiclient import discovery

class GoogleDriveManager:
    """Google Drive integration for managing PDF files."""
    
    def __init__(self, drive_client):
        self.drive_client = drive_client

    def get_ward_metadata(self):
        """Get metadata for all ward PDF files."""
        # Implement the logic to fetch ward metadata from Google Drive
        # Example:
        # return {
        #     "ward_1": {"display_name": "Ward 1", "filename": "ward_1_records.pdf", "patients": {...}},
        #     ...
        # }
        # ...existing code...

    def initialize_service(self):
        """Initialize Google Drive API service with robust error handling."""
        try:
            print("Initializing Google Drive service...")
            creds = None
            
            # Try both token locations
            token_locations = [self.token_path, self.alt_token_path]
            for token_path in token_locations:
                if os.path.exists(token_path):
                    print(f"Found token file at: {token_path}")
                    try:
                        print(f"Loading token from {token_path} (standard way)")
                        with open(token_path, 'rb') as token:
                            creds = pickle.load(token)
                        print(f"Credential type: {type(creds)}")
                        print(f"Token valid: {creds.valid}")
                        print(f"Token expired: {creds.expired}")
                        print(f"Has refresh token: {'Yes' if creds.refresh_token else 'No'}")
                        if creds.valid:
                            print("Successfully loaded credentials")
                            break
                    except Exception as e:
                        print(f"Error loading token from {token_path}: {str(e)}")
            
            # If no valid credentials found, try to refresh or create new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    print("Refreshing expired token")
                    try:
                        creds.refresh(Request())
                        print("Token refreshed successfully")
                    except Exception as e:
                        print(f"Error refreshing token: {str(e)}")
                        return False
                else:
                    # If no credentials or refresh failed, need new credentials
                    print("No valid credentials found")
                    return False
            
            # Create the Drive service with a timeout and error retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.drive_service = discovery.build(
                        'drive', 'v3', 
                        credentials=creds,
                        cache_discovery=False
                    )
                    print("Google Drive service initialized successfully")
                    
                    # Save the updated token to both locations
                    for token_path in token_locations:
                        try:
                            with open(token_path, 'wb') as token:
                                pickle.dump(creds, token)
                        except Exception as e:
                            print(f"Warning: Could not save token to {token_path}: {str(e)}")
                    
                    return True
                except Exception as e:
                    print(f"Attempt {attempt+1}/{max_retries} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retrying
                    else:
                        print(f"Error initializing Google Drive service: {str(e)}")
                        return False
            
            return self.drive_service is not None
                
        except Exception as e:
            print(f"Error initializing Google Drive service: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def list_pdf_files(self):
        """List all PDF files in the configured folder."""
        if not self.drive_service:
            if not self.initialize_service():
                print("Failed to initialize Google Drive service")
                return []
        
        try:
            query = f"'{self.folder_id}' in parents and mimeType='application/pdf'"
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                pageSize=1000
            ).execute()
            
            files = results.get('files', [])
            return files
        except Exception as e:
            print(f"Error listing PDF files: {str(e)}")
            return []
    
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

    def get_local_path(self, file_id, filename):
        """Get the local path for a file, downloading it if necessary."""
        cache_dir = "/tmp/pdf_cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create a deterministic filename based on the file_id
        local_path = os.path.join(cache_dir, f"{file_id}_{os.path.basename(filename)}")
        
        # Check if file already exists and is not empty
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            print(f"Using cached file: {local_path}")
            return local_path
        
        # Need to download the file
        try:
            print(f"Downloading {filename} from Google Drive...")
            if not self.drive_service and not self.initialize_service():
                print("Failed to initialize Google Drive service")
                return None
            
            request = self.drive_service.files().get_media(fileId=file_id)
            
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Download {int(status.progress() * 100)}%")
            
            print(f"File cached at {local_path}")
            
            # Verify the downloaded file
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                return local_path
            else:
                print(f"Downloaded file is empty or missing")
                return None
                
        except Exception as e:
            print(f"Error downloading file: {str(e)}")
            import traceback
            traceback.print_exc()
            if os.path.exists(local_path):
                os.remove(local_path)
            return None
