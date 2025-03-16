#!/bin/bash

# This script is used by Render to start the application

echo "Starting application on Render..."

# Check if we have the token file
TOKEN_DIR="/tmp/pdf_cache"
TOKEN_PATH="${TOKEN_DIR}/token.pickle"

if [ ! -d "$TOKEN_DIR" ]; then
    echo "Creating token directory..."
    mkdir -p "$TOKEN_DIR"
fi

# If we have a base64-encoded token, decode it
if [ -n "$GOOGLE_TOKEN_BASE64" ]; then
    echo "Found base64-encoded token, decoding to $TOKEN_PATH"
    echo "$GOOGLE_TOKEN_BASE64" | base64 -d > "$TOKEN_PATH"
    echo "Token decoded successfully"
fi

# Check if token.pickle exists
if [ -f "$TOKEN_PATH" ]; then
    echo "Token file found at $TOKEN_PATH"
else
    echo "Token file not found at $TOKEN_PATH"
    echo "Please upload the token.pickle file to the Render instance."
    exit 1
fi

# Print environment status (without revealing secrets)
echo "Checking environment variables..."
[ -n "$GOOGLE_CLIENT_ID" ] && echo "GOOGLE_CLIENT_ID is set" || echo "GOOGLE_CLIENT_ID is not set"
[ -n "$GOOGLE_CLIENT_SECRET" ] && echo "GOOGLE_CLIENT_SECRET is set" || echo "GOOGLE_CLIENT_SECRET is not set"
[ -n "$GOOGLE_REDIRECT_URI" ] && echo "GOOGLE_REDIRECT_URI is set" || echo "GOOGLE_REDIRECT_URI is not set"
[ -n "$GOOGLE_DRIVE_FOLDER_ID" ] && echo "GOOGLE_DRIVE_FOLDER_ID is set" || echo "GOOGLE_DRIVE_FOLDER_ID is not set"

# Start the application with Gunicorn
echo "Starting Gunicorn server..."
gunicorn --workers 2 --bind 0.0.0.0:$PORT --timeout 120 wsgi:app
