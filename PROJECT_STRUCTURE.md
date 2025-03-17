# Project Structure Documentation

This document outlines the structure of the PDF Split application and explains how the components interact.

## Core Components

### 1. Database Models (`models.py`)
Contains SQLAlchemy models for data persistence:
- `User`: Application users with authentication info
- `AuditLog`: Tracking of user actions
- `RecentlyViewedPatient`: User's recently viewed patients
- `CareNote`: Notes entered by users for patients
- `Settings`: Application settings

### 2. PDF Processing (`pdf_processor.py`)
Handles extraction of patient data from PDFs:
- `extract_patient_info()`: Extracts patient information and care notes
- `extract_patients_from_text()`: Alternative method for PDFs without bookmarks
- `process_ward_pdf()`: Main function to process a PDF and extract all patient data

### 3. Ward Management (`ward_manager.py`)
Manages ward data and coordinates with PDF processing:
- `WardManager`: Class for managing ward data and metadata
  - `get_ward_metadata()`: Gets ward metadata from Google Drive or local files
  - `load_specific_ward()`: Loads data for a specific ward
  - `load_ward_patients()`: Loads patient data for a ward
  - `get_patient_info_from_ward_data()`: Gets patient info across all wards

### 4. Flask Application (`app.py`)
Main application entry point with routes and controllers:
- User authentication routes
- Ward and patient view routes
- Search functionality
- Care notes management
- Admin features

### 5. Google Drive Integration (`simple_drive.py`)
Handles Google Drive integration:
- `SimpleDriveClient`: Client for Google Drive API
  - `initialize()`: Sets up Google Drive API connection
  - `get_local_path()`: Downloads a file from Google Drive
  - `get_ward_metadata()`: Gets metadata for ward PDFs in Google Drive

## Data Flow

1. **Authentication Flow**:
   - User logs in via `/login` route
   - Session is created and user is redirected to index or default ward

2. **Ward Data Loading Flow**:
   - `ward_manager.init_ward_data()` loads metadata from Google Drive or local files
   - When a ward is accessed, `ward_manager.load_specific_ward()` loads patient data
   - `pdf_processor.process_ward_pdf()` extracts data from the PDF

3. **Patient Data Flow**:
   - Patient data is stored in memory in `ward_manager.wards_data`
   - Care notes are stored in the database via SQLAlchemy models
   - Patient views are tracked in the `RecentlyViewedPatient` table

## Dependency Structure

