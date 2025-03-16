# PDF Split Application

A Flask application for managing and viewing patient data from ward PDF files.

## Local Setup with Gunicorn

1. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Create a `pdf_files` directory and add your PDF files**:
   ```
   mkdir pdf_files
   ```
   Download PDF files from the Google Drive link and place them in this directory.
   
   Alternatively, you can set the `PDF_DIRECTORY` environment variable to point to another location.

3. **Run the application using Gunicorn**:
   ```
   ./run_local.sh
   ```
   Or directly with:
   ```
   gunicorn --config gunicorn_config.py wsgi:app
   ```

4. **Access the application** at http://localhost:8000

## Deployment on Render

1. **Fork or clone this repository** to your GitHub account.

2. **Create a new Web Service** in your Render dashboard.

3. **Link your GitHub repository** to the Render service.

4. **Configure environment variables**:
   - `SECRET_KEY`: A secure random string
   - `SESSION_COOKIE_SECURE`: Set to `True` for production
   - `PDF_DIRECTORY`: Set to the directory where PDFs are stored on Render

5. **Upload your PDF files** to the specified directory in your Render service.

## PDF Files

PDF files should be named in the format `ward_X_records.pdf` where X is the ward identifier.
