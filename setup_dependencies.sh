#!/bin/bash

echo "Installing required Python packages..."

# Install the core dependencies
pip install --upgrade pip
pip install python-dotenv google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install flask flask-login flask-sqlalchemy flask-wtf werkzeug sqlalchemy reportlab PyPDF2
pip install xlsxwriter gunicorn

echo "Installation complete!"
echo "Now, run ./run_auth.sh to authenticate with Google Drive."
