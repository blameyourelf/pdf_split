#!/usr/bin/env python3
"""
Utility to create a properly formatted token for Render deployment.
"""
import os
import sys
import json
import base64
import pickle
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

def main():
    """Create a properly formatted token from environment variables."""
    print("Creating Google Drive token file...")
    
    # Get OAuth credentials from environment
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    
    # Check required variables
    if not all([client_id, client_secret, redirect_uri, refresh_token]):
        print("Error: Missing required environment variables!")
        print("Make sure you have the following set in your .env file:")
        print("- GOOGLE_CLIENT_ID")
        print("- GOOGLE_CLIENT_SECRET")
        print("- GOOGLE_REDIRECT_URI")
        print("- GOOGLE_REFRESH_TOKEN (this is the important one!)")
        return 1
    
    # Create credentials object
    try:
        creds = Credentials(
            None,  # No token
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Force a refresh to ensure it's working
        creds.refresh(None)
        print("Successfully refreshed token!")
        
        # Save as a pickle file
        token_pickle = 'token.pickle'
        with open(token_pickle, 'wb') as f:
            pickle.dump(creds, f)
        print(f"Credentials saved to {token_pickle}")
        
        # Save as JSON for debugging
        token_json = 'token.json'
        with open(token_json, 'w') as f:
            json_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            json.dump(json_data, f, indent=2)
        print(f"Credentials also saved as JSON to {token_json}")
        
        # Create base64 version
        with open(token_pickle, 'rb') as f:
            token_data = f.read()
        
        token_b64 = base64.b64encode(token_data).decode('utf-8')
        with open('token_base64.txt', 'w') as f:
            f.write(token_b64)
        print("Base64-encoded token saved to token_base64.txt")
        print("\nCopy this base64 string to your GOOGLE_TOKEN_BASE64 environment variable in Render:")
        print("-" * 40)
        print(token_b64[:50] + "..." + token_b64[-10:])
        print("-" * 40)
        
        return 0
    except Exception as e:
        print(f"Error creating credentials: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
