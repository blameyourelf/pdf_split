# Contingency EPR Digital Notes Viewer

## Overview
The Contingency EPR Digital Notes Viewer is a web application designed to manage and view electronic patient records (EPR) in a hospital setting. It provides functionalities for viewing patient information, adding care notes, exporting notes, and managing session timeouts.

## Main Features
- **Patient Records Management**: View and manage patient records, including demographics, vitals, and care notes.
- **Care Notes**: Add, view, and search care notes for patients.
- **Export Functionality**: Export notes to PDF and Excel formats.
- **Session Timeout**: Configure session timeout settings to automatically log out inactive users.
- **User Preferences**: Set default wards for users.
- **Audit Log**: View audit logs for user actions.

## Dependencies
The project relies on several Python packages and other dependencies:
- `flask==2.0.1`
- `flask-sqlalchemy==2.5.1`
- `flask-login==0.5.0`
- `PyPDF2==3.0.1`
- `werkzeug==2.0.1`
- `sqlalchemy==1.4.23`
- `reportlab==4.0.4`
- `flask-wtf==1.2.1`
- `xlsxwriter==3.1.2`

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

## Usage
1. Initialize the database:
    ```sh
    flask init-db
    ```
2. Run the application:
    ```sh
    flask run
    ```
3. Access the application in your web browser at `http://127.0.0.1:5000`.

## Configuration
- **Session Timeout**: Configure session timeout settings in the admin dashboard.
- **Export Settings**: Ensure `xlsxwriter` is installed for Excel export functionality.

## File Structure
- `app.py`: Main application file containing routes and logic.
- `templates/`: Directory containing HTML templates.
- `static/`: Directory containing static files (CSS, JS).
- `models/`: Directory containing database models.
- `generate_pdf.py`: Script for generating PDF files.
- `generate_long_stay_ward.py`: Script for generating long stay ward PDFs.
- `requirements.txt`: List of project dependencies.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed.
