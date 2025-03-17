# Creating a Valid Google Drive Token for Render

Follow these steps to generate a properly formatted token for Render deployment:

## 1. Get a Refresh Token

You can get a refresh token using the Google OAuth 2.0 Playground:

1. Go to: https://developers.google.com/oauthplayground/
2. Click the gear icon in the top right corner and check "Use your own OAuth credentials"
3. Enter your OAuth 2.0 client ID and client secret
4. Close the settings panel
5. In the left panel, scroll down and select "Drive API v3" and check "https://www.googleapis.com/auth/drive.readonly"
6. Click "Authorize APIs"
7. Log in with your Google account and authorize the application
8. On the next screen, click "Exchange authorization code for tokens"
9. In the response, find the "refresh_token" value

## 2. Add the Refresh Token to Your Environment

Add this refresh token to your `.env` file:

