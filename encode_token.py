#!/usr/bin/env python3
import os
import sys
import base64
import tempfile

def main():
    """Encode token.pickle to base64 for Render deployment."""
    # Look for token in multiple locations
    possible_paths = [
        os.path.join(tempfile.gettempdir(), 'pdf_cache', 'token.pickle'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token.pickle')
    ]
    
    token_path = None
    for path in possible_paths:
        if os.path.exists(path):
            token_path = path
            print(f"Found token file at: {path}")
            break
    
    if not token_path:
        print("Error: token.pickle not found. Please run auth_drive.py first.")
        return 1
    
    # Encode the token to base64
    try:
        with open(token_path, 'rb') as f:
            token_data = f.read()
        
        encoded = base64.b64encode(token_data).decode('utf-8')
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token_base64.txt')
        
        with open(output_path, 'w') as f:
            f.write(encoded)
        
        print(f"Token encoded successfully and saved to: {output_path}")
        print(f"Contents of {output_path} should be added as GOOGLE_TOKEN_BASE64 environment variable in Render")
        return 0
    except Exception as e:
        print(f"Error encoding token: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
