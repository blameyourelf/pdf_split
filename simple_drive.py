"""
A simplified Google Drive client that avoids the circular import issues
by using direct HTTP requests instead of the discovery API.
"""
import os
import io
import pickle
import base64
import requests
import json
import time
import tempfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

class SimpleDriveClient:
    """A simplified Google Drive client that uses direct API access."""
    
    def __init__(self):
        self.token = None
        # Use a more reliable approach for token paths
        self.cache_dir = os.path.join(tempfile.gettempdir(), 'pdf_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.token_path = os.path.join(os.getcwd(), 'token.pickle')
        self.alt_token_path = os.path.join(self.cache_dir, 'token.pickle')
        
        # Ensure the cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load credentials from base64 encoded token if available
        encoded_token = os.environ.get('GOOGLE_TOKEN_BASE64')
        if encoded_token:
            try:
                token_data = base64.b64decode(encoded_token)
                with open(self.token_path, 'wb') as token_file:
                    token_file.write(token_data)
                with open(self.alt_token_path, 'wb') as token_file:
                    token_file.write(token_data)
                print(f"Decoded token saved to {self.token_path} and {self.alt_token_path}")
            except Exception as e:
                print(f"Error decoding token: {str(e)}")
    
    def initialize(self):
        """Initialize the client and ensure we have a valid access token."""
        print("Initializing Simple Drive client...")
        creds = None
        
        # Try both token locations
        token_locations = [self.token_path, self.alt_token_path]
        for token_path in token_locations:
            if os.path.exists(token_path):
                print(f"Found token file at: {token_path}")
                try:
                    with open(token_path, 'rb') as token:
                        creds = pickle.load(token)
                    print(f"Token valid: {creds.valid}")
                    print(f"Token expired: {creds.expired}")
                    print(f"Has refresh token: {'Yes' if creds.refresh_token else 'No'}")
                    if creds.valid:
                        self.token = creds
                        break
                except Exception as e:
                    print(f"Error loading token from {token_path}: {str(e)}")
        
        # If token is expired but has refresh token, try to refresh
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token")
            try:
                creds.refresh(Request())
                print("Token refreshed successfully")
                self.token = creds
                
                # Save the updated token to both locations
                for token_path in token_locations:
                    try:
                        with open(token_path, 'wb') as token:
                            pickle.dump(creds, token)
                    except Exception as e:
                        print(f"Warning: Could not save token to {token_path}: {str(e)}")
            except Exception as e:
                print(f"Error refreshing token: {str(e)}")
                return False
        
        return self.token is not None

    def list_files(self, folder_id, mime_type=None):
        """List files in a Google Drive folder using direct API requests."""
        if not self.token:
            if not self.initialize():
                print("Failed to initialize token")
                return []
        
        try:
            url = 'https://www.googleapis.com/drive/v3/files'
            query = f"'{folder_id}' in parents"
            if mime_type:
                query += f" and mimeType='{mime_type}'"
            
            params = {
                'q': query,
                'fields': 'files(id,name,mimeType)',
                'pageSize': 1000
            }
            
            headers = {
                'Authorization': f"Bearer {self.token.token}",
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get('files', [])
            else:
                print(f"Error listing files: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Error listing files: {str(e)}")
            return []

    def download_file(self, file_id, destination_path):
        """Download a file from Google Drive using direct API requests."""
        if not self.token:
            if not self.initialize():
                print("Failed to initialize token")
                return False
        
        try:
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            headers = {
                'Authorization': f"Bearer {self.token.token}"
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Stream the download to handle large files
            with requests.get(url, headers=headers, stream=True) as response:
                if response.status_code == 200:
                    with open(destination_path, 'wb') as f:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = int(100 * downloaded / total_size)
                                    print(f"Download {percent}%")
                    
                    print(f"File downloaded to: {destination_path}")
                    return True
                else:
                    print(f"Error downloading file: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"Error downloading file: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def get_ward_metadata(self, folder_id):
        """Get metadata for all ward PDF files in a folder."""
        wards_meta = {}
        
        print("Fetching files from Google Drive folder...")
        files = self.list_files(folder_id, mime_type='application/pdf')
        
        if not files:
            print("No PDF files found in Google Drive folder")
            print(f"Folder ID: {folder_id}")
            return {}
        
        print(f"Found {len(files)} PDF files in Google Drive")    
        for file in files:
            filename = file['name']
            print(f"Processing file: {filename}")
            if filename.startswith('ward_') and filename.endswith('_records.pdf'):
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
        
        local_path = os.path.join(cache_dir, f"{file_id}_{os.path.basename(filename)}")
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            print(f"Using cached file: {local_path}")
            return local_path
        
        print(f"Downloading {filename} from Google Drive...")
        if self.download_file(file_id, local_path):
            return local_path
        else:
            return None
