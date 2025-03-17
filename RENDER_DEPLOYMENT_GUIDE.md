# Deploying to Render: Step-by-Step Guide

This guide provides detailed instructions for deploying this application to Render with Google Drive integration.

## 1. Local Setup

First, make sure your application works locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your Google credentials
cp .env.template .env
# Edit .env with your Google credentials

# Authenticate with Google Drive
python auth_drive.py
# This will open a browser window and create token.pickle

# Test your setup
python test_google_drive.py
# If this works, you're ready to prepare for Render
```

## 2. Prepare for Render Deployment

Generate a base64-encoded version of your token:

```bash
# Create the encode_token.py script:
cat > encode_token.py << 'EOL'
import os
import tempfile
import base64

# Path to your token.pickle file
token_dir = os.path.join(tempfile.gettempdir(), 'pdf_cache')
token_path = os.path.join(token_dir, 'token.pickle')
alt_token_path = './token.pickle'

# Find the token file
if os.path.exists(token_path):
    path_to_use = token_path
elif os.path.exists(alt_token_path):
    path_to_use = alt_token_path
else:
    raise FileNotFoundError("token.pickle not found. Run auth_drive.py first.")

# Read and encode the token
with open(path_to_use, 'rb') as f:
    token_data = f.read()
    token_b64 = base64.b64encode(token_data).decode('utf-8')

# Write to file
with open('token_base64.txt', 'w') as f:
    f.write(token_b64)

print(f"Token encoded and saved to token_base64.txt")
print(f"Token length: {len(token_b64)} characters")
print("Use this value for the GOOGLE_TOKEN_BASE64 environment variable in Render")
EOL

# Run the script to encode your token
python encode_token.py
```

This creates `token_base64.txt` containing your encoded token.

## 3. Set up Render

1. Create a new Web Service in Render
2. Connect to your GitHub repository
3. Configure the service:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt && chmod +x start_render.sh`
   - **Start Command**: `./start_render.sh`

4. Add the following environment variables:
   - `GOOGLE_CLIENT_ID`: Your Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET`: Your Google OAuth client secret  
   - `GOOGLE_REDIRECT_URI`: Your Render app URL (e.g., https://your-app.onrender.com)
   - `GOOGLE_DRIVE_FOLDER_ID`: Your Google Drive folder ID with PDF files
   - `GOOGLE_TOKEN_BASE64`: Copy the contents of your `token_base64.txt` file
   - `SECRET_KEY`: Generate a random secret key (e.g., run `python -c "import secrets; print(secrets.token_hex(16))"`)
   - `SESSION_COOKIE_SECURE`: Set to `True`
   - `PDF_DIRECTORY`: Set to `/tmp/pdf_cache`

## 4. Deploy

Click "Create Web Service" and wait for the deployment to complete.

The `start_render.sh` script will:
1. Set up the token
2. Create necessary directories
3. Run diagnostics
4. Initialize the database if needed
5. Start the application with Gunicorn

## 5. Troubleshooting

If your app isn't connecting to Google Drive:

1. Check Render logs for errors
2. Verify all environment variables are set correctly
3. Make sure your Google Drive folder contains PDF files with the correct naming format
4. Check that the token was decoded correctly (logs should show "Token successfully decoded")
5. Try regenerating your token locally and re-encoding it

If your database isn't initializing properly:

1. Connect to the Render shell and run:
   ```
   python -c "from app import app, db; app.app_context().push(); db.create_all(); db.create_all(bind=['audit'])"
   ```

2. Check for errors in the logs related to database initialization

## 6. Refreshing Your Token

Google Drive tokens expire. If your token stops working:

1. Re-authenticate locally with `python auth_drive.py`
2. Re-encode the token with `python encode_token.py` 
3. Update the `GOOGLE_TOKEN_BASE64` environment variable in Render

## 7. Monitoring

Use Render's logging features to monitor your application:

1. Check the application logs in the Render dashboard
2. Look for errors related to Google Drive authentication or PDF processing
3. Monitor any warnings about missing PDF files
