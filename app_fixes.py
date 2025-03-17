"""
This file contains suggestions to clean up formatting and fix potential issues in app.py.
"""

# 1. Fix duplicate imports:
# The following import section has duplicates that should be consolidated:

"""
import os
import threading
from urllib.parse import unquote
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
from flask_wtf.csrf import CSRFProtect
import click
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import lru_cache
import re
from urllib.parse import quote, unquote  # 'unquote' is imported twice
from flask.cli import with_appcontext
import io
import csv
import tempfile
# Duplicate import of datetime and timedelta
from datetime import datetime, timedelta
# Duplicate import of flask components
from flask import (Flask, render_template, request, jsonify, redirect, 
                  url_for, flash, session, make_response, send_file)
from sqlalchemy import desc
from dotenv import load_dotenv
"""

# Should be consolidated to:

"""
import os
import re
import io
import csv
import threading
import tempfile
import subprocess
import click
from functools import lru_cache
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
from flask import (Flask, render_template, request, jsonify, redirect, 
                  url_for, flash, session, make_response, send_file)
from flask.cli import with_appcontext
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import scoped_session, sessionmaker
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from dotenv import load_dotenv
from simple_drive import SimpleDriveClient
"""

# 2. Function load_specific_ward appears to be defined twice (around lines 548 and 573)
# Suggestion: Keep only one definition and update as needed

# 3. The drive_client initialization has potential issues:
"""
# Replace this:
drive_client = SimpleDriveClient()
print("Simple Drive client created")

# And this in before_first_request:
if not drive_client:
    drive_client = SimpleDriveClient()
drive_client.initialize()

# With a more robust pattern:
drive_client = None

def get_drive_client():
    global drive_client
    if drive_client is None:
        drive_client = SimpleDriveClient()
        initialized = drive_client.initialize()
        if not initialized:
            print("Warning: Failed to initialize drive client")
    return drive_client

@app.before_first_request
def before_first_request():
    """Initialize data before first request."""
    # Initialize the drive client
    get_drive_client()
    # Initialize ward data
    init_ward_data()
"""

# 4. The session timeout check has indentation issues that should be fixed:
"""
@app.before_request
def check_session_timeout():
    """Improved session timeout check with better debugging"""
    if current_user.is_authenticated and request.endpoint not in ['static', 'logout']:
        if get_timeout_enabled():
            try:
                last_active = session.get('last_active')
                if last_active is None:
                    # Set initial timestamp if missing
                    session['last_active'] = datetime.utcnow().timestamp()
                    return
                
                # Debug output
                print(f"Session timeout check: Last active = {last_active}, Current user: {current_user.username}")
                
                timeout_minutes = get_timeout_minutes()
                last_active_dt = datetime.fromtimestamp(float(last_active))
                time_diff = datetime.utcnow() - last_active_dt
                time_diff_minutes = time_diff.total_seconds() / 60
                
                print(f"Time difference: {time_diff_minutes:.2f} minutes, Timeout: {timeout_minutes} minutes")
                
                if time_diff > timedelta(minutes=timeout_minutes):
                    print(f"Session timed out for {current_user.username}")
                    logout_user()
                    flash('Your session has expired due to inactivity')
                    return redirect(url_for('login'))
                
                # Update last_active timestamp
                session['last_active'] = datetime.utcnow().timestamp()
            except Exception as e:
                # Log any errors during timeout check
                print(f"Session timeout error: {str(e)}")
                # Reset the timestamp to prevent logout loops
                session['last_active'] = datetime.utcnow().timestamp()
"""

# 5. There are inconsistent patterns for error handling. 
# Standardize error handling with try/except blocks and explicit error messages:

"""
# Example of improved error handling pattern for route functions:
@app.route('/ward/<ward_num>')
@login_required
def ward(ward_num):
    """Ward view route handler"""
    try:
        global wards_data
        # URL decode the ward_num to handle special characters
        ward_num = unquote(ward_num)
        
        print(f"Accessing ward: {ward_num}")
        print(f"Available wards: {list(wards_data.keys())}")
        
        # Normalize ward number/name
        normalized_ward = ward_num
        if ward_num.lower().startswith('ward '):
            normalized_ward = ward_num[5:].strip()  # Remove 'ward ' prefix
        
        # Reload ward metadata if empty
        if not wards_data:
            print("Ward data is empty, reloading metadata...")
            init_ward_data()
            
        # Try loading the ward data
        if normalized_ward in wards_data:
            success = load_specific_ward(normalized_ward)
            print(f"Load ward data result: {success}")
            
        # Add audit log entry
        log_access('view_ward', f'Ward {normalized_ward}')
        
        # Check if ward exists after all loading attempts
        if normalized_ward not in wards_data:
            print(f"Ward not found in wards_data: {normalized_ward}")
            flash("Ward not found", "error")
            return redirect(url_for('index'))
        
        # Get ward info
        ward_info = wards_data[normalized_ward]
        
        # Get PDF creation time (file modification time)
        pdf_creation_time = "Unknown"
        try:
            if "file_id" in ward_info:
                file_id = ward_info["file_id"]
                local_path = get_drive_client().get_local_path(file_id, ward_info["filename"])
                if local_path and os.path.exists(local_path):
                    pdf_mtime = os.path.getmtime(local_path)
                    pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
            elif os.path.exists(ward_info["filename"]):
                pdf_mtime = os.path.getmtime(ward_info["filename"])
                pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Error getting file info: {str(e)}")
        
        # Render the ward template
        return render_template('ward.html', 
                             ward_num=normalized_ward,
                             ward_data={"patients": ward_info.get("patients", {})},
                             pdf_filename=ward_info["filename"],
                             pdf_creation_time=pdf_creation_time,
                             display_name=ward_info.get("display_name", normalized_ward))
    except Exception as e:
        print(f"Error in ward route: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"An error occurred loading ward data: {str(e)}", "error")
        return redirect(url_for('index'))
"""

# 6. There's a mix of print statements and more structured logging.
# Consider replacing print statements with a more consistent logging approach:

"""
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Then replace print statements like:
print(f"Loading specific ward: {ward_num}")

# With:
logger.info(f"Loading specific ward: {ward_num}")

# And errors like:
print(f"Error loading ward {ward_num}: {str(e)}")

# With:
logger.error(f"Error loading ward {ward_num}: {str(e)}")
"""

# 7. Global variables should be better managed:
"""
# Define all globals at the top with clear documentation
# Current globals spread throughout the file:
wards_data = {}
is_loading_data = False
PDF_DIRECTORY = os.path.join(os.getcwd(), 'pdfs')
drive_client = SimpleDriveClient()
EXCEL_EXPORT_AVAILABLE = False

# Better approach with documentation:
# Application globals
wards_data = {}           # Storage for ward metadata and patient info
is_loading_data = False   # Flag to track background loading status
drive_client = None       # Google Drive client, initialized lazily
EXCEL_EXPORT_AVAILABLE = False  # Flag for Excel export capability

# Configuration with environment fallbacks
PDF_DIRECTORY = os.environ.get('PDF_DIRECTORY', os.path.join(os.getcwd(), 'pdfs'))
"""

# 8. The app.py file is very long (1700+ lines) and should be split into modules:
"""
# Consider splitting the file into:
# - models.py: User, AuditLog, RecentlyViewedPatient, CareNote, Settings models
# - auth.py: Authentication related routes and functions
# - ward_routes.py: Routes for ward and patient viewing
# - admin_routes.py: Admin routes and functionality
# - export_handlers.py: PDF and Excel export functionality
# - drive_integration.py: Google Drive integration code
# - utils.py: Utility functions like timeout handlers
"""
