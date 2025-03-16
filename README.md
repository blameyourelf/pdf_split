# PDF Split Application with Google Drive Integration

A Flask application for managing and viewing patient data from ward PDF files, with support for both local files and Google Drive.

## Setup Instructions

1. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

2. **Configure Google Drive access:**
   
   Create a `.env` file in the project root with the following content:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret 
   GOOGLE_REDIRECT_URI=https://your-app-url.com
   GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
   ```

3. **Authenticate with Google Drive:**
   ```
   python auth_drive.py
   ```
   This will open a browser window to authorize your application to access the Google Drive folder.

4. **Run the application:**
   
   With Gunicorn (recommended for production-like environment):
   ```
   ./run_with_gunicorn.sh
   ```
   
   Or for development:
   ```
   python app.py
   ```

5. **Access the application:**
   Open your browser and visit http://localhost:8000

## Using Google Drive for PDF Files

1. Upload your PDF files to the Google Drive folder specified in the `GOOGLE_DRIVE_FOLDER_ID` environment variable.
2. Files should be named in the format `ward_X_records.pdf` where X is the ward identifier.
3. The application will automatically download and cache files from Google Drive when needed.

## Deployment to Render

1. Fork or clone this repository to your GitHub account
2. Create a new Web Service in Render
3. Set the following environment variables:
   - `GOOGLE_CLIENT_ID`: Your Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET`: Your Google OAuth client secret
   - `GOOGLE_REDIRECT_URI`: Your Render app URL
   - `GOOGLE_DRIVE_FOLDER_ID`: Your Google Drive folder ID
4. Set the build command to: `pip install -r requirements.txt`
5. Set the start command to: `gunicorn wsgi:app`

**Important**: For deployment, you'll need to manually upload the token file (`token.pickle`) to your Render instance or use the Render shell to run the authorization script.
