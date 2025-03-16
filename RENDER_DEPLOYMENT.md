# Deploying to Render

This guide provides detailed instructions for deploying this application to Render.

## Prerequisites

1. Create a Render account: https://render.com/
2. Have your Google Drive API credentials ready

## Deployment Steps

### 1. Fork or Clone the Repository

If you're starting from a local project, push it to GitHub first.

### 2. Create a New Web Service in Render

1. Go to your Render Dashboard
2. Click "New" and select "Web Service"
3. Connect your GitHub repository
4. Choose the repository containing this application

### 3. Configure the Web Service

Fill in the following settings:

- **Name**: pdf-split-app (or your preferred name)
- **Environment**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `./start_render.sh`
- **Plan Type**: Choose an appropriate plan (Free tier works for testing)

### 4. Set Environment Variables

Set these environment variables:

- `GOOGLE_CLIENT_ID`: Your Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Your Google OAuth client secret
- `GOOGLE_REDIRECT_URI`: Your Render app URL (e.g., https://pdf-split-app.onrender.com)
- `GOOGLE_DRIVE_FOLDER_ID`: The ID of your Google Drive folder with PDF files
- `GOOGLE_TOKEN_BASE64`: Base64-encoded token (see below)

### 5. Generate and Encode the Google Drive Token

To work without browser interaction on Render, you need to get the authentication token locally:

1. Run authentication locally first:
   ```
   ./run_auth.sh
   ```

2. Encode the token file to base64:
   ```
   cat /tmp/pdf_cache/token.pickle | base64 > token_base64.txt
   ```

3. Copy the base64 content from token_base64.txt and set it as the `GOOGLE_TOKEN_BASE64` environment variable in Render.

### 6. Deploy

Click "Create Web Service" and wait for the deployment to complete.

## Troubleshooting

If you encounter issues:

1. Check the logs in Render dashboard
2. Verify all environment variables are set correctly
3. Make sure your Google Drive folder contains PDFs with the correct naming convention
4. Test authentication locally before deploying
