from google_drive import GoogleDriveManager
import os
import sys
import tempfile

def test_drive():
    """Test Google Drive integration."""
    print("Testing Google Drive integration...")
    manager = GoogleDriveManager()
    
    # Print environment settings (without showing actual values)
    for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI', 'GOOGLE_DRIVE_FOLDER_ID']:
        if os.environ.get(var):
            print(f"✓ {var}: configured")
        else:
            print(f"✗ {var}: missing")
    
    # Check token file
    token_path = os.path.join(os.path.join(tempfile.gettempdir(), 'pdf_cache'), 'token.pickle')
    if os.path.exists(token_path):
        print(f"✓ Token file exists at: {token_path}")
    else:
        print(f"✗ Token file not found at: {token_path}")
        print("Please run auth_drive.py first to authenticate.")
        return False
    
    # Initialize the drive service
    print("\nInitializing Google Drive service...")
    if not manager.initialize_service():
        print("Failed to initialize Google Drive service")
        return False
    
    print("\nFetching files from Google Drive folder...")
    # List files in the folder
    files = manager.list_pdf_files()
    print(f"Found {len(files)} PDF files in Google Drive folder")
    
    if not files:
        print("No PDF files found. Please check your Google Drive folder ID.")
        return False
    
    # Display file names
    for file in files:
        print(f"File: {file['name']} (ID: {file['id']})")
    
    # Test downloading the first file
    if files:
        test_file = files[0]
        print(f"\nTesting download of {test_file['name']}...")
        local_path = manager.get_local_path(test_file['id'], test_file['name'])
        if local_path:
            print(f"✓ Successfully downloaded file to {local_path}")
            # Check file size to verify it downloaded correctly
            size = os.path.getsize(local_path)
            print(f"File size: {size} bytes")
            return True
        else:
            print("✗ Failed to download file")
            return False
    
    return True

if __name__ == "__main__":
    success = test_drive()
    sys.exit(0 if success else 1)
