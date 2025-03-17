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

## 4. Deploy

Click "Create Web Service" and wait for the deployment to complete.

## 5. Troubleshooting

If your app isn't connecting to Google Drive:

1. Check Render logs for errors
2. Verify all environment variables are set correctly
3. Make sure your Google Drive folder contains PDF files with the correct naming format
4. Check that the token was decoded correctly (logs should show "Token successfully decoded")
5. Try regenerating your token locally and re-encoding it
