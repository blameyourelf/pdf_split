#!/bin/bash

echo "Starting application on Render..."

# Setup token directory
TOKEN_DIR="/tmp/pdf_cache"
TOKEN_PATH="${TOKEN_DIR}/token.pickle"

if [ ! -d "$TOKEN_DIR" ]; then
    echo "Creating token directory..."
    mkdir -p "$TOKEN_DIR"
fi

# Print environment status (without revealing secrets)
echo "Checking environment variables..."
[ -n "$GOOGLE_CLIENT_ID" ] && echo "✓ GOOGLE_CLIENT_ID is set" || echo "✗ GOOGLE_CLIENT_ID is not set"
[ -n "$GOOGLE_CLIENT_SECRET" ] && echo "✓ GOOGLE_CLIENT_SECRET is set" || echo "✗ GOOGLE_CLIENT_SECRET is not set"
[ -n "$GOOGLE_REDIRECT_URI" ] && echo "✓ GOOGLE_REDIRECT_URI is set" || echo "✗ GOOGLE_REDIRECT_URI is not set"
[ -n "$GOOGLE_DRIVE_FOLDER_ID" ] && echo "✓ GOOGLE_DRIVE_FOLDER_ID is set" || echo "✗ GOOGLE_DRIVE_FOLDER_ID is not set"
[ -n "$GOOGLE_TOKEN_BASE64" ] && echo "✓ GOOGLE_TOKEN_BASE64 is set" || echo "✗ GOOGLE_TOKEN_BASE64 is not set"

# If we have a base64-encoded token in an environment variable, decode it
if [ -n "$GOOGLE_TOKEN_BASE64" ]; then
    echo "Found base64-encoded token, decoding to $TOKEN_PATH"
    echo "$GOOGLE_TOKEN_BASE64" | base64 -d > "$TOKEN_PATH"
    if [ -f "$TOKEN_PATH" ]; then
        echo "✓ Token successfully decoded and saved to $TOKEN_PATH"
        ls -la "$TOKEN_PATH"
    else
        echo "✗ Failed to create token file at $TOKEN_PATH"
    fi
else
    echo "No GOOGLE_TOKEN_BASE64 environment variable found"
fi

# Create PDF directory if it doesn't exist
mkdir -p ./pdf_files

# Start the application with Gunicorn
echo "Starting Gunicorn server..."
gunicorn --workers 2 --bind 0.0.0.0:$PORT --timeout 120 wsgi:app
