# PDF Split Application with Google Drive Integration

A Flask application for managing and viewing patient data from ward PDF files, with support for both local files and Google Drive. The application allows healthcare professionals to view patient information from PDF ward reports, add care notes, and track patient interactions.

## Features

- View patient data extracted from PDF ward reports
- Add care notes for patients
- Track recently viewed patients
- Search across wards and patients
- Admin dashboard for audit logs and care notes management
- Google Drive integration for PDF storage
- Excel and PDF export of care notes

## Architecture

This application has been refactored to use a modular architecture:

- **Database Models**: SQLAlchemy models for data storage
- **PDF Processing**: Module for extracting data from PDFs
- **Ward Management**: Module for coordinating ward data
- **Google Drive Integration**: Module for accessing files in Google Drive
- **Flask Web Application**: Routes and controllers

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed architecture documentation.

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account with API credentials (for Google Drive integration)
- PDF files in the format `ward_X_records.pdf` where X is the ward identifier

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/pdf-split.git
   cd pdf-split
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   Create a `.env` file in the project root:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:5000
   GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
   SECRET_KEY=your-secret-key
   PDF_DIRECTORY=./pdf_files
   ```

4. **Authenticate with Google Drive** (if using Drive integration):
   ```bash
   python auth_drive.py
   ```
   This will open a browser window to authorize your application.

5. **Initialize the database**:
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all(); db.create_all(bind=['audit'])"
   ```

### Running the Application

#### Local Development

```bash
python app.py
```

#### Production with Gunicorn

```bash
./run_with_gunicorn.sh
```

Access the application at http://localhost:8000 (or port 5000 for development).

## Using Google Drive for PDF Files

1. Upload your PDF files to the Google Drive folder specified in the `GOOGLE_DRIVE_FOLDER_ID` environment variable.
2. Files should be named in the format `ward_X_records.pdf` where X is the ward identifier.
3. The application will automatically download and cache files from Google Drive when needed.

## Local PDF Files

If not using Google Drive, place your PDF files in the directory specified by the `PDF_DIRECTORY` environment variable (default: `./pdf_files`).

## Deployment to Render

For detailed instructions on deploying to Render, see:
- [RENDER_DEPLOYMENT_GUIDE.md](RENDER_DEPLOYMENT_GUIDE.md) - Step-by-step guide
- [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) - Quick reference

## Running Tests

Run all tests with:
```bash
python run_tests.py
```

Run individual test suites:
```bash
python test_database.py
python test_ward_manager.py
python test_pdf_processor.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | (required for Drive) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | (required for Drive) |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI | (required for Drive) |
| `GOOGLE_DRIVE_FOLDER_ID` | ID of Drive folder with PDFs | (required for Drive) |
| `PDF_DIRECTORY` | Local directory for PDFs | `./pdf_files` |
| `SECRET_KEY` | Flask secret key | (required) |
| `SESSION_COOKIE_SECURE` | Secure cookies | `False` |

## Demo Credentials

For testing purposes, the following credentials are available:
- **Admin**: Username: `admin`, Password: `admin123`
- **Nurse**: Username: `nurse1`, Password: `nurse123`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
