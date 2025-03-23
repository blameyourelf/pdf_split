# Contingency EPR Digital Notes Viewer

## Overview
The Contingency EPR Digital Notes Viewer is a Flask web application designed to serve as a backup system for hospital Electronic Patient Records (EPR). It allows healthcare providers to view patient information and add care notes during main EPR system downtime.

## Main Features
- **Database-Driven Architecture**: Patient records, wards, and notes are stored in a SQL database
- **Care Notes Management**: Add, view, and search continuous care notes for patients
- **Ward Navigation**: Access patients by ward with intuitive interface
- **User Management**: Admin controls for creating and managing user accounts
- **Note Templates**: Predefined templates for common note types
- **My Shift Notes**: Track notes added during your shift for later transcription
- **Audit Logging**: Complete history of system actions for accountability
- **PDF/Excel Export**: Export notes in multiple formats
- **Session Timeout**: Configurable automatic logout for security

## Dependencies
The project relies on several Python packages:
- `flask==2.0.1`
- `flask-sqlalchemy==2.5.1`
- `flask-login==0.5.0`
- `PyPDF2==3.0.1`
- `werkzeug==2.0.1`
- `sqlalchemy==1.4.23`
- `reportlab==4.0.4`
- `flask-wtf==1.2.1`
- `xlsxwriter==3.1.2` (optional, for Excel exports)

## Installation
1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/pdf_split.git
    cd pdf_split
    ```
2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Initial Setup
1. Place ward PDF files in the project root directory:
   - Files should be named `ward_X_records.pdf` where X is the ward number or name
   - Example: `ward_1_records.pdf`, `ward_Pediatrics_records.pdf`

2. Initialize the project:
    ```sh
    python initialize_project.py
    ```
   This will:
   - Back up any existing databases
   - Create all required database tables
   - Apply necessary database indexes
   - Create initial admin and user accounts
   - Configure default system settings
   - Process ward PDF files

3. Default login credentials:
   - Admin: username: `admin`, password: `admin123`
   - Nurse: username: `nurse1`, password: `nurse123`

   **Important**: Change these passwords immediately after first login

## Usage
1. Start the application:
    ```sh
    python app.py
    ```
   or
    ```sh
    flask run
    ```
2. Access the application at `http://127.0.0.1:5000`
3. Login with the default admin credentials (you should change these):
   - Username: `admin`
   - Password: `changeme`

## Deployment Notes
- Configure a proper production database for persistent storage
- Set a strong SECRET_KEY in app.py
- Set up proper WSGI server (gunicorn, uwsgi) for production use
- Configure server environment variables as needed

## File Structure
- `app.py`: Main application file with routes and core logic
- `models.py`: Database models (patients, wards, users, notes)
- `templates/`: HTML templates for the UI
- `static/`: CSS, JavaScript and other static assets
- `migrations/`: Database migration scripts
- `init_db.py`: Database initialization script

## Data Migration
The system supports loading data from:
- Direct database entries
- PDF patient records (using the provided migration tools)

## Security Notes
- Change default credentials immediately
- Configure session timeout settings in the admin dashboard
- Regularly backup the database
