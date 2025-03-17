#!/usr/bin/env python3
"""
Diagnostic tool to check Google Drive connection and available PDF files.
"""
import os
import sys
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Run diagnostics on Google Drive integration."""
    print("Google Drive Diagnostics Tool")
    print("=============================")
    
    # Check environment variables
    print("\n1. Checking environment variables:")
    for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI', 'GOOGLE_DRIVE_FOLDER_ID']:
        value = os.environ.get(var)
        if value:
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '****'
            print(f"  ✓ {var} is set: {masked}")
        else:
            print(f"  ✗ {var} is NOT set")
    
    # Check token file
    print("\n2. Checking token file:")
    temp_dir = tempfile.gettempdir()
    token_path = os.path.join(temp_dir, 'pdf_cache', 'token.pickle')
    token_path_alt = os.path.join('.', 'token.pickle')
    
    if os.path.exists(token_path):
        print(f"  ✓ Token file found at: {token_path}")
        print(f"    Last modified: {datetime.fromtimestamp(os.path.getmtime(token_path)).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Size: {os.path.getsize(token_path)} bytes")
    elif os.path.exists(token_path_alt):
        print(f"  ✓ Token file found at: {token_path_alt}")
        print(f"    Last modified: {datetime.fromtimestamp(os.path.getmtime(token_path_alt)).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Size: {os.path.getsize(token_path_alt)} bytes")
    else:
        print(f"  ✗ Token file not found at: {token_path} or {token_path_alt}")
    
    # Initialize Google Drive
    print("\n3. Initializing Google Drive service:")
    try:
        from google_drive import GoogleDriveManager
        
        drive = GoogleDriveManager()
        if drive.initialize_service():
            print("  ✓ Google Drive service initialized successfully")
            
            # List files
            print("\n4. Listing files in Google Drive folder:")
            files = drive.list_pdf_files()
            if files:
                print(f"  Found {len(files)} files in Google Drive folder:")
                for i, file in enumerate(files, 1):
                    print(f"  {i}. {file['name']} (ID: {file['id']})")
                    
                # Try downloading the first file
                if len(files) > 0:
                    print("\n5. Testing file download:")
                    test_file = files[0]
                    local_path = drive.get_local_path(test_file['id'], test_file['name'])
                    if local_path:
                        print(f"  ✓ Successfully downloaded file to: {local_path}")
                        print(f"    File size: {os.path.getsize(local_path)} bytes")
                    else:
                        print("  ✗ Failed to download file")
            else:
                print("  ✗ No files found in Google Drive folder")
            
            # Get ward metadata
            print("\n6. Getting ward metadata:")
            wards = drive.get_ward_metadata()
            if wards:
                print(f"  Found {len(wards)} wards:")
                for ward_id, ward_info in wards.items():
                    print(f"  - {ward_id}: {ward_info['display_name']} (File: {ward_info['filename']})")
            else:
                print("  ✗ No wards found")
        else:
            print("  ✗ Failed to initialize Google Drive service")
    except Exception as e:
        print(f"  ✗ Error initializing Google Drive: {str(e)}")
    
    print("\nDiagnostics complete.")
    
if __name__ == "__main__":
    main()
