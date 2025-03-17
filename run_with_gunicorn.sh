#!/bin/bash

# Color codes for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Preparing to run the PDF Split application with Gunicorn...${NC}"

# Load environment variables from .env if it exists
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env file${NC}"
    export $(grep -v '^#' .env | xargs)
fi

# Check for Google Drive token
TOKEN_PATH="/tmp/pdf_cache/token.pickle"
LOCAL_TOKEN_PATH="$(pwd)/token.pickle"

if [ ! -f "$TOKEN_PATH" ] && [ ! -f "$LOCAL_TOKEN_PATH" ] && [ -n "$GOOGLE_DRIVE_FOLDER_ID" ]; then
    echo -e "${YELLOW}Google Drive token not found at $TOKEN_PATH or $LOCAL_TOKEN_PATH${NC}"
    echo -e "${YELLOW}Running authentication first...${NC}"
    
    # Run the authentication script
    python -c "
import os
import pickle
import tempfile
from google_auth_oauthlib.flow import InstalledAppFlow

# Set up the OAuth flow
client_config = {
    'installed': {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': [os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost')],
    }
}

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

try:
    # Run the authorization flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    # Save the credentials
    token_dir = os.path.join(tempfile.gettempdir(), 'pdf_cache')
    os.makedirs(token_dir, exist_ok=True)
    token_path = os.path.join(token_dir, 'token.pickle')

    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)
    print(f'Token saved to: {token_path}')

    # Also save to current directory
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    print(f'Token also saved to: token.pickle')
except Exception as e:
    print(f'Error during authentication: {str(e)}')
    exit(1)
"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Authentication failed. Please try again.${NC}"
        echo -e "${YELLOW}Do you want to continue anyway? (y/n)${NC}"
        read -r answer
        if [[ "$answer" != "y" ]]; then
            echo -e "${RED}Exiting.${NC}"
            exit 1
        fi
    fi
fi

# Fix the 'get_static_doc' issue by creating a patch for the drive service
echo -e "${YELLOW}Creating patch for Google Drive API...${NC}"

python -c "
import os

# Create the patch directory if it doesn't exist
patch_dir = os.path.expanduser('~/.googleapiclient')
os.makedirs(patch_dir, exist_ok=True)

# Create the __init__.py file if it doesn't exist
init_file = os.path.join(patch_dir, '__init__.py')
if not os.path.exists(init_file):
    with open(init_file, 'w') as f:
        f.write('# Google API Client patch directory\\n')

# Create the patched discovery.py file
discovery_file = os.path.join(patch_dir, 'discovery.py')
with open(discovery_file, 'w') as f:
    f.write('''
# Patched discovery module to avoid get_static_doc issue
from googleapiclient import discovery as original_discovery

# Patch the build function
original_build = original_discovery.build

def patched_build(*args, **kwargs):
    # Force static_discovery to be False to avoid the get_static_doc error
    kwargs['static_discovery'] = False
    return original_build(*args, **kwargs)

# Replace the original build function with our patched version
original_discovery.build = patched_build
''')

print('Created patch for Google Drive API')
"

# Create PDF directory if it doesn't exist
PDF_DIR="${PDF_DIRECTORY:-./pdf_files}"
mkdir -p "$PDF_DIR"
echo -e "${GREEN}PDF directory set to: $PDF_DIR${NC}"

# Run with Gunicorn
echo -e "${GREEN}Starting application with Gunicorn...${NC}"
PYTHONPATH="$PYTHONPATH:~/.googleapiclient" gunicorn --workers 2 --bind 0.0.0.0:8000 --timeout 120 wsgi:app
