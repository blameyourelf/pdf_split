# Database Migration Guide

This guide explains how to migrate from parsing PDFs at runtime to using a SQLite database with pre-parsed data.

## Overview

The current approach of parsing PDFs from Google Drive at runtime has several limitations:
- Performance issues with large PDFs
- Dependency on Google Drive availability
- Higher server resource utilization
- Slower initial page loads

The new database-driven approach offers these advantages:
- Improved performance with pre-parsed data
- Reduced runtime dependencies on Google Drive
- Lower resource utilization
- Faster page loads
- More reliable patient data retrieval

## Migration Steps

### 1. Set Up the Database Schema

First, create the database schema by running:

```bash
# Create the database schema
python database_schema.py
```

This will create an SQLite database with tables for wards, patients, and care notes.

### 2. Populate the Database with PDF Data

There are two ways to populate the database:

#### Option A: Process Google Drive PDFs

```bash
# Download PDFs from Google Drive and parse them into the database
python pdf_to_db.py --google-drive
```

#### Option B: Process Local PDFs

```bash
# Parse local PDFs into the database
python pdf_to_db.py --pdf-directory /path/to/pdfs
```

### 3. Integrate Database Routes into the Flask Application

In your `app.py` file, add the following imports at the top:

```python
from db_manager import db_manager
from db_routes import register_routes
```

Add the database configuration to your Flask app:

```python
# Configure database
app.config['DB_PATH'] = os.environ.get('DB_PATH', 'instance/patient_data.db')

# Register database routes
register_routes(app)
```

### 4. Update Existing Routes to Use the Database

Replace your existing routes that load data from PDFs with database-powered versions. Examples are provided in the `integration_guide.py` file.

Key routes to update:
- Ward display route (`/ward/<ward_num>`)
- Patient display route (`/patient/<patient_id>`)
- Search routes
- Care notes handling

### 5. Update Deployment Process

Modify your deployment process to initialize the database during deployment:

1. Add a database initialization script:
   
   ```bash
   # initialize_database.sh
   echo "Initializing database..."
   python -m database_schema
   
   echo "Processing PDFs and populating database..."
   python -m pdf_to_db --google-drive
   
   echo "Database initialization complete"
   ```

2. Update your `start_render.sh` file:
   
   ```bash
   #!/bin/bash
   
   # Check if database exists, if not initialize it
   if [ ! -f "instance/patient_data.db" ]; then
       echo "Database not found, initializing..."
       bash initialize_database.sh
   fi
   
   # Start the application
   gunicorn --workers=2 --threads=4 --timeout=60 wsgi:app
   ```

3. Make the scripts executable:
   
   ```bash
   chmod +x initialize_database.sh
   chmod +x start_render.sh
   ```

### 6. Add Environment Variables

Update your `.env` file or environment variables:

