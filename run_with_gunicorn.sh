#!/bin/bash

# Load environment variables from .env if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Check for Google Drive token
TOKEN_PATH=$(python -c "import tempfile, os; print(os.path.join(tempfile.gettempdir(), 'pdf_cache', 'token.pickle'))")
if [ ! -f "$TOKEN_PATH" ]; then
    echo "Google Drive token not found at $TOKEN_PATH"
    echo "Running authentication first..."
    python auth_drive.py
    if [ $? -ne 0 ]; then
        echo "Authentication failed. Please try again."
        exit 1
    fi
fi

# Test Google Drive connectivity
echo "Testing Google Drive connectivity..."
python test_google_drive.py
if [ $? -ne 0 ]; then
    echo "Google Drive connection test failed."
    echo "Do you want to continue anyway? (y/n)"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo "Exiting."
        exit 1
    fi
fi

# Run with Gunicorn
echo "Starting application with Gunicorn..."
gunicorn --workers 2 --bind 0.0.0.0:8000 --timeout 120 wsgi:app
