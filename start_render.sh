#!/bin/bash

echo "===== Starting application on Render ====="
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo "Working directory: $(pwd)"

# Setup token directory
TOKEN_DIR="/tmp/pdf_cache"
TOKEN_PATH="${TOKEN_DIR}/token.pickle"
ROOT_TOKEN_PATH="./token.pickle"

if [ ! -d "$TOKEN_DIR" ]; then
    echo "Creating token directory..."
    mkdir -p "$TOKEN_DIR"
    echo "Created directory: $TOKEN_DIR"
fi

# Print environment status (without revealing secrets)
echo "Checking environment variables..."
[ -n "$GOOGLE_CLIENT_ID" ] && echo "✓ GOOGLE_CLIENT_ID is set" || echo "✗ GOOGLE_CLIENT_ID is not set"
[ -n "$GOOGLE_CLIENT_SECRET" ] && echo "✓ GOOGLE_CLIENT_SECRET is set" || echo "✗ GOOGLE_CLIENT_SECRET is not set"
[ -n "$GOOGLE_REDIRECT_URI" ] && echo "✓ GOOGLE_REDIRECT_URI is set" || echo "✗ GOOGLE_REDIRECT_URI is not set"
[ -n "$GOOGLE_DRIVE_FOLDER_ID" ] && echo "✓ GOOGLE_DRIVE_FOLDER_ID is set" || echo "✗ GOOGLE_DRIVE_FOLDER_ID is not set"
[ -n "$GOOGLE_TOKEN_BASE64" ] && echo "✓ GOOGLE_TOKEN_BASE64 is set" || echo "✗ GOOGLE_TOKEN_BASE64 is not set"

# Check for Python and pip
echo "Checking Python installation..."
which python && python --version
which pip && pip --version

# If we have a base64-encoded token in an environment variable, decode it
if [ -n "$GOOGLE_TOKEN_BASE64" ]; then
    echo "Found base64-encoded token, decoding to both locations"
    echo "$GOOGLE_TOKEN_BASE64" | base64 -d > "$TOKEN_PATH"
    echo "$GOOGLE_TOKEN_BASE64" | base64 -d > "$ROOT_TOKEN_PATH"
    
    if [ -f "$TOKEN_PATH" ]; then
        echo "✓ Token successfully decoded and saved to $TOKEN_PATH"
        ls -la "$TOKEN_PATH"
        echo "File contents (first 20 bytes, hex):"
        hexdump -n 20 -C "$TOKEN_PATH"
    else
        echo "✗ Failed to create token file at $TOKEN_PATH"
    fi
    
    if [ -f "$ROOT_TOKEN_PATH" ]; then
        echo "✓ Token also saved to $ROOT_TOKEN_PATH"
    else
        echo "✗ Failed to create token file at $ROOT_TOKEN_PATH"
    fi
else
    echo "No GOOGLE_TOKEN_BASE64 environment variable found"
fi

# Create PDF directory if it doesn't exist
mkdir -p ./pdf_files
echo "Created PDF directory"

# Create log directory
mkdir -p ./logs
echo "Created logs directory"

# Run diagnostics
echo "Running Google Drive diagnostics..."
python check_google_drive.py > ./logs/drive_diagnostics.log 2>&1
echo "Diagnostics completed. See logs/drive_diagnostics.log for details."

# Start the application with Gunicorn
echo "Starting Gunicorn server..."
export PYTHONUNBUFFERED=1
exec gunicorn --workers 2 --log-level debug --bind 0.0.0.0:$PORT --timeout 120 --error-logfile ./logs/error.log --access-logfile ./logs/access.log wsgi:app
