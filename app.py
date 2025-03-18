from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
from flask_wtf.csrf import CSRFProtect
import os
import threading
import click
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import lru_cache
import re
from urllib.parse import quote, unquote
from flask.cli import with_appcontext
import io
import csv
from datetime import datetime, timedelta
from sqlalchemy import desc

# Try to import xlsxwriter but don't fail if not available
try:
    import xlsxwriter
    EXCEL_EXPORT_AVAILABLE = True
except ImportError:
    EXCEL_EXPORT_AVAILABLE = False

# Improve XlsxWriter detection with better error handling
EXCEL_EXPORT_AVAILABLE = False
try:
    import xlsxwriter
    # Actually test creating a workbook to verify it works
    test_buffer = io.BytesIO()
    test_workbook = xlsxwriter.Workbook(test_buffer)
    test_workbook.close()
    EXCEL_EXPORT_AVAILABLE = True
    print("Excel export functionality is available")
except Exception as e:
    print(f"Excel export will be disabled: {str(e)}")
    
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import subprocess
from datetime import datetime

from models import (
    db, User, AuditLog, Patient, Note, Ward, 
    Settings, get_notes_enabled, get_timeout_enabled, get_timeout_minutes
)
from utils.logger import setup_logger
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-8712'  # Change this in production
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)  # Limit session lifetime
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Main database for users
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_BINDS'] = {
    'audit': 'sqlite:///audit.db'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Replace the SQLALCHEMY_ENGINE_OPTIONS configuration
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'connect_args': {'check_same_thread': False}
}

# Fix app configuration for sessions
# Place this near the top of your file where other app.config settings are
app.config['SESSION_COOKIE_SECURE'] = False  # Temporarily disable for local testing
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

# Initialize extensions
db.init_app(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize login manager with improved configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.session_protection = "strong"

# Add this after creating the Flask app but before the routes
@app.context_processor
def inject_year():
    return {'year': datetime.utcnow().year}

def get_git_info():
    try:
        # Get last commit date
        last_commit_date = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cd', '--date=format:%B %Y'], 
            encoding='utf-8'
        ).strip()
        return {
            'last_updated': last_commit_date or 'March 2024'  # Fallback if no git info
        }
    except Exception:
        return {
            'last_updated': 'March 2024'  # Fallback if git command fails
        }

@app.context_processor
def inject_template_vars():
    return {
        'year': datetime.utcnow().year,
        'git_info': get_git_info()
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def log_access(action, patient_id=None):
    """Fix log_access to handle cases where user might not be authenticated"""
    try:
        if current_user.is_authenticated:
            log = AuditLog(
                user_id=current_user.id,
                username=current_user.username,
                action=action,
                patient_id=patient_id,
            )
            db.session.add(log)
            try:
                # Using a separate commit to ensure the audit record is saved
                db.session.commit()
                print(f"Audit log entry created: {action} for {patient_id}")
            except Exception as e:
                # If there's an error, rollback but continue (don't prevent the main action)
                db.session.rollback()
                print(f"Error logging audit entry: {str(e)}")
    except Exception as e:
        print(f"Error in log_access: {str(e)}")

# Dictionary to store ward data
wards_data = {}

# Flag to indicate if data is being loaded
is_loading_data = False

def extract_patient_info(pdf_path, patient_id=None):
    """Extract patient info and notes while supporting multiple note formats"""
    patient_data = {}
    current_patient = None
    current_patient_id = None
    try:
        reader = PdfReader(pdf_path)
        for page_idx in range(len(reader.pages)):
            page = reader.pages[page_idx]
            text = page.extract_text()
            # Check if this is a new patient record
            if "Patient Record - Ward" in text:
                # Save previous patient if exists
                if current_patient_id and current_patient:
                    if not patient_id or current_patient_id == patient_id:
                        patient_data[current_patient_id] = current_patient
                # Reset for new patient
                current_patient = {
                    "info": {},
                    "name": "Unknown",
                    "vitals": "",
                    "care_notes": []
                }
                current_patient_id = None
                in_care_notes = False
            # Extract patient ID - MUST do this for all patients
            if current_patient and not current_patient_id:
                id_match = re.search(r"Patient ID:\s*(\d+)", text)
                if id_match:
                    current_patient_id = id_match.group(1).strip()
            # If we found the specific patient we're looking for, or we want all patients
            if not patient_id or (current_patient_id and (current_patient_id == patient_id)):
                # Extract name if we haven't yet
                if current_patient and current_patient["name"] == "Unknown":
                    name_match = re.search(r"Name:\s*([^\n]+)", text)
                    if name_match:
                        current_patient["name"] = name_match.group(1).strip()
                # Extract ward if we haven't yet
                if current_patient and "Ward" not in current_patient["info"]:
                    ward_match = re.search(r"Ward:\s*([^\n]+)", text)
                    if ward_match:
                        current_patient["info"]["Ward"] = ward_match.group(1).strip()
                # Extract DOB if we haven't yet
                if current_patient and "DOB" not in current_patient["info"]:
                    dob_match = re.search(r"DOB:\s*([^\n]+)", text)
                    if dob_match:
                        current_patient["info"]["DOB"] = dob_match.group(1).strip()
                # Check for care notes section
                if "Continuous Care Notes" in text and not in_care_notes:
                    in_care_notes = True
                # Extract care notes if we're in that section
                if in_care_notes and current_patient:
                    # If we're continuing from a previous page, just use the whole text
                    care_notes_text = text
                    if "Continuous Care Notes" in text:
                        # If this page has the header, extract notes from after that
                        care_notes_section = text.split("Continuous Care Notes", 1)
                        if len(care_notes_section) > 1:
                            care_notes_text = care_notes_section[1].strip()
                    else:
                        # If we're continuing from previous page, use the whole text
                        care_notes_text = text
                    # Check if there's a header row on this page
                    if "Date & Time" in care_notes_text and "Staff Member" in care_notes_text and "Notes" in care_notes_text:
                        # Remove header row
                        header_pos = care_notes_text.find("Notes")
                        if header_pos > 0:
                            header_end = care_notes_text.find("\n", header_pos)
                            if header_end > 0:
                                care_notes_text = care_notes_text[header_end:].strip()
                    # Now process the actual notes - try the long notes format first
                    care_notes_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+([^,]+(?:, [A-Z]+)?)\s+(.+?)(?=(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2})|$)"
                    matches = list(re.finditer(care_notes_pattern, care_notes_text, re.DOTALL))
                    if matches:
                        # Long notes format worked
                        for match in matches:
                            date = match.group(1).strip()
                            staff = match.group(2).strip()
                            note = match.group(3).strip()
                            if date and staff and note:
                                current_patient["care_notes"].append({
                                    "date": date,
                                    "staff": staff,
                                    "note": note
                                })
                    else:
                        # Try alternative format - splitting by lines and looking for date patterns
                        lines = care_notes_text.split('\n')
                        i = 0
                        while i < len(lines):
                            # Skip empty lines
                            if not lines[i].strip():
                                i += 1
                                continue
                            # Look for date time pattern at start of line
                            date_match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", lines[i].strip())
                            if date_match:
                                date = date_match.group(1)
                                # Extract rest of line after date
                                line_parts = lines[i][len(date):].strip().split("  ", 1)
                                if len(line_parts) > 1:
                                    staff = line_parts[0].strip()
                                    note_start = line_parts[1].strip()
                                    # Check for multi-line notes
                                    note_lines = [note_start]
                                    j = i + 1
                                    while j < len(lines) and not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", lines[j].strip()):
                                        if lines[j].strip():  # Only add non-empty lines
                                            note_lines.append(lines[j].strip())
                                        j += 1
                                    full_note = "\n".join(note_lines)
                                    current_patient["care_notes"].append({
                                        "date": date,
                                        "staff": staff,
                                        "note": full_note
                                    })
                                    i = j - 1  # Move to the last processed line
                            i += 1
        # Handle last patient
        if current_patient_id and current_patient:
            if not patient_id or current_patient_id == patient_id:
                patient_data[current_patient_id] = current_patient
        return patient_data
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def process_patient_data(info_lines):
    demographics = {}
    care_notes = []
    in_care_notes = False
    header_found = False
    try:
        for line in info_lines:
            line = line.strip()
            if not line:
                continue
            # Check for care notes section
            if "Continuous Care Notes" in line:
                in_care_notes = True
                continue
            # Skip the header row of the care notes table
            if in_care_notes and not header_found and "Date & Time" in line:
                header_found = True
                continue
            if not in_care_notes:
                # Process demographics fields
                fields = {
                    "Patient ID:": "Patient ID",
                    "Name:": "Name",
                    "Ward:": "Ward",
                    "DOB:": "DOB",
                }
                for prefix, key in fields.items():
                    if prefix in line:
                        value = line.split(prefix, 1)[1].strip()
                        demographics[key] = value
            elif in_care_notes and header_found:
                # Process care notes - expecting date, staff member, and note
                parts = [p.strip() for p in line.split("  ") if p.strip()]
                if len(parts) >= 3:
                    care_notes.append({
                        "date": parts[0],
                        "staff": parts[1],
                        "note": " ".join(parts[2:])
                    })
                elif len(parts) == 2:
                    care_notes.append({
                        "date": parts[0],
                        "staff": parts[1],
                        "note": ""
                    })
        # Ensure we have a name
        if "Name" not in demographics:
            demographics["Name"] = "Unknown"
        patient_data = {
            "info": demographics,
            "name": demographics.get("Name", "Unknown"),
            "vitals": "",
            "care_notes": care_notes
        }
        return patient_data
    except Exception as e:
        return {
            "info": {"Name": "Error Processing Patient"},
            "name": "Error Processing Patient",
            "vitals": "",
            "care_notes": []
        }

# Get ward metadata without processing patient data
def get_ward_metadata():
    import re
    wards_meta = {}
    ward_files = [f for f in os.listdir('.') if f.startswith('ward_') and f.endswith('_records.pdf')]
    for pdf_filename in ward_files:
        # Extract ward name/number between 'ward_' and '_records.pdf'
        ward_part = pdf_filename[5:-12]  # Remove 'ward_' and '_records.pdf'
        # For numbered wards that use Long_X format
        if ward_part.startswith('Long_'):
            display_name = f"Long {ward_part[5:]}"  # Convert Long_1 to "Long 1"
        # For numeric ward names, prepend "Ward"
        elif ward_part.isdigit():
            display_name = f"Ward {ward_part}"
        else:
            display_name = ward_part  # Keep special ward names as is
        wards_meta[ward_part] = {
            "filename": pdf_filename,
            "display_name": display_name,
            "patients": {}  # Empty placeholder, will be filled on demand
        }
    # Sort wards
    sorted_ward_nums = sorted(wards_meta.keys(), key=lambda x: wards_meta[x]["display_name"].lower())
    sorted_wards_meta = {}
    for ward_num in sorted_ward_nums:
        sorted_wards_meta[ward_num] = wards_meta[ward_num]
    return sorted_wards_meta

# Process a single ward PDF, with caching
@lru_cache(maxsize=2)  # Reduce cache size to prevent memory issues
def process_ward_pdf(pdf_filename):
    if os.path.exists(pdf_filename):
        try:
            patient_info = extract_patient_info(pdf_filename)
            return patient_info
        except Exception as e:
            print(f"Error processing {pdf_filename}: {str(e)}")
            return {}
    return {}

# Load a specific ward's data
def load_specific_ward(ward_num):
    global wards_data
    # Always clear cache when loading a ward
    process_ward_pdf.cache_clear()
    if ward_num in wards_data:
        pdf_filename = wards_data[ward_num]["filename"]
        patient_data = process_ward_pdf(pdf_filename)
        wards_data[ward_num]["patients"] = patient_data
    else:
        pass

def load_ward_data_background():
    global wards_data, is_loading_data
    # First load metadata only (fast)
    wards_data = get_ward_metadata()
    is_loading_data = False

# Start with just the metadata
def init_ward_data():
    global wards_data, is_loading_data
    is_loading_data = True
    threading.Thread(target=load_ward_data_background).start()
    is_loading_data = False

# Initialize with metadata
init_ward_data()

# Add this function to properly load ward patients data if not already loaded
def load_ward_patients(ward_num):
    """Load patient data for a specific ward."""
    global wards_data
    if ward_num in wards_data:
        # Only load if not already loaded
        if not wards_data[ward_num].get("patients") or len(wards_data[ward_num]["patients"]) == 0:
            pdf_filename = wards_data[ward_num].get("filename")
            if pdf_filename and os.path.exists(pdf_filename):
                try:
                    # Clear cache to ensure fresh data
                    process_ward_pdf.cache_clear()
                    patient_data = process_ward_pdf(pdf_filename)
                    wards_data[ward_num]["patients"] = patient_data
                    return True
                except Exception as e:
                    print(f"Error loading patients for ward {ward_num}: {str(e)}")
                    return False
        return True  # Already loaded
    return False  # Ward not found

# Update load_specific_ward to use the new function
def load_specific_ward(ward_num):
    """Load a specific ward's data (wrapper around load_ward_patients)"""
    return load_ward_patients(ward_num)

# Replace the load_ward_patients function with a more efficient version
def load_ward_patients(ward_num):
    """Load patient data for a specific ward, but only if needed."""
    global wards_data
    if ward_num in wards_data:
        # Only load if patients aren't already loaded
        if not wards_data[ward_num].get("patients") or len(wards_data[ward_num]["patients"]) == 0:
            pdf_filename = wards_data[ward_num].get("filename")
            if pdf_filename and os.path.exists(pdf_filename):
                try:
                    process_ward_pdf.cache_clear()
                    patient_data = process_ward_pdf(pdf_filename)
                    wards_data[ward_num]["patients"] = patient_data
                    return True
                except Exception as e:
                    print(f"Error loading patients for ward {ward_num}: {str(e)}")
                    return False
        return True  # Already loaded
    return False  # Ward not found

# Add a new function to get patient information efficiently
def get_patient_info_from_ward_data(patient_id, ward_id=None):
    """
    Get patient name and ward name from ward data efficiently.
    Returns tuple of (patient_name, ward_name, ward_id)
    """
    # If we know the ward, check it directly first
    if ward_id and ward_id in wards_data:
        if not wards_data[ward_id].get("patients"):
            load_ward_patients(ward_id)
        ward_info = wards_data[ward_id]
        patients = ward_info.get("patients", {})
        if patient_id in patients:
            return (
                patients[patient_id].get("name", "Unknown"),
                ward_info.get("display_name", ward_id),
                ward_id
            )
    # Try to find patient in frequently used wards first
    # This optimizes for common wards to avoid loading all wards
    frequently_used_wards = []
    # Get recently viewed wards by this user
    recent_views = RecentlyViewedPatient.query.filter_by(user_id=current_user.id).all()
    for rv in recent_views:
        if rv.ward_num and rv.ward_num not in frequently_used_wards:
            frequently_used_wards.append(rv.ward_num)
    # Check frequent wards first
    for ward_num in frequently_used_wards:
        if ward_num in wards_data:
            if not wards_data[ward_num].get("patients"):
                load_ward_patients(ward_num)
            ward_info = wards_data[ward_num]
            patients = ward_info.get("patients", {})
            if patient_id in patients:
                return (
                    patients[patient_id].get("name", "Unknown"),
                    ward_info.get("display_name", ward_num),
                    ward_num
                )
    # If not found in frequent wards, check remaining wards as needed
    for ward_num, ward_info in wards_data.items():
        if ward_num in frequently_used_wards:
            continue  # Skip already checked wards
        if not ward_info.get("patients"):
            load_ward_patients(ward_num)
        patients = ward_info.get("patients", {})
        if patient_id in patients:
            return (
                patients[patient_id].get("name", "Unknown"),
                ward_info.get("display_name", ward_num),
                ward_num
            )
    # Not found in any ward
    return ("Unknown", "Unknown", None)

# Fix the login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Enhanced login with debugging"""
    # If already logged in, go to index
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Login attempt for username: {username}")
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User found in database: {user.username}, ID: {user.id}")
            password_match = check_password_hash(user.password_hash, password)
            print(f"Password match: {password_match}")
            if password_match:
                print(f"Login successful for {user.username}")
                login_user(user, remember=True)
                session.permanent = True
                session['last_active'] = datetime.utcnow().timestamp()
                # Add additional session data to help with debugging
                session['user_id'] = user.id
                session['login_time'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                log_access('login')
                next_page = request.args.get('next')
                if next_page and not next_page.startswith('/'):
                    next_page = None
                return redirect(next_page or url_for('index'))
        # Only flash message if login failed
        flash('Invalid username or password')
                
    return render_template('login.html')

@app.after_request
def add_security_headers(response):
    # Existing headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Add Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "style-src 'self' https://cdnjs.cloudflare.com https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

@app.route('/logout', methods=['POST'])  # Change to POST only
@login_required
def logout():
    log_access('logout')
    # Clear any existing flash messages before logging out
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('login'))

# Add a GET route that shows a confirmation page
@app.route('/logout', methods=['GET'])
@login_required
def logout_page():
    return render_template('logout.html')  # Create this template with a form

# Fix the index route to confirm login status
@app.route('/')
@login_required
def index():
    """Modified index route with explicit login check and debug info"""
    # Debug output to confirm we're authenticated
    print(f"Index accessed by: {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    print(f"Current user authenticated: {current_user.is_authenticated}")
    print(f"Session data: {session}")
    # Explicitly cast to boolean and check for '1'
    show_all = request.args.get('show_all') == '1'
    
    # Only redirect to default ward if show_all is False AND user has a default ward
    if current_user.default_ward and not show_all:
        return redirect(url_for('ward', ward_num=current_user.default_ward))
    # If show_all is True, or user has no default ward, show all wards
    sorted_wards = {}
    for ward_id, info in sorted(wards_data.items(), key=lambda x: x[1]['display_name'].lower()):
        sorted_wards[ward_id] = info
    return render_template('index.html', wards=sorted_wards, show_all=show_all)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Remove any note-related flash messages that might have persisted
    session.pop('_flashes', None)
    if request.method == 'POST':
        default_ward = request.form.get('default_ward')
        user = User.query.get(current_user.id)
        user.default_ward = default_ward
        db.session.commit()
        flash('Default ward updated successfully', 'success')
        return redirect(url_for('profile'))
    wards = get_ward_metadata()
    return render_template('profile.html', 
                         wards=wards,
                         current_ward=current_user.default_ward)

@app.route('/ward/<ward_num>')
@login_required
def ward(ward_num):
    # URL decode the ward_num to handle special characters
    ward_num = unquote(ward_num)
    # Get ward from database instead of PDF
    ward = Ward.query.filter_by(ward_number=ward_num).first_or_404()
    
    # Get all patients in this ward
    patients = Patient.query.filter_by(current_ward=ward_num, is_active=True).all()
    
    # Format patient data for template
    patient_list = [
        {"id": patient.hospital_id, "name": patient.name}
        for patient in patients
    ]
    log_access('view_ward', f'Ward {ward_num}')
    return render_template('ward.html',
                         ward_num=ward_num,
                         ward_data={"patients": {p["id"]: p for p in patient_list}},
                         pdf_filename=ward.pdf_file,
                         pdf_creation_time=ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward.last_updated else "Unknown")

@app.route('/search_ward/<ward_num>')
@login_required
def search_ward(ward_num):
    ward_num = unquote(ward_num)
    if ward_num not in wards_data:
        return jsonify([])
    search_query = request.args.get('q', '').strip().lower()
    ward_patients = wards_data[ward_num].get("patients", {})
    # If no search query, return all patients
    if not search_query:
        results = [{"id": pid, "name": data["name"]}
                  for pid, data in ward_patients.items()]
    else:
        # Search in both ID and name
        results = [{"id": pid, "name": data["name"]}
                  for pid, data in ward_patients.items() 
                  if search_query in pid.lower() or 
                     search_query in data["name"].lower()]
    return jsonify(results)

@app.route('/search_wards')
@login_required
def search_wards():
    query = request.args.get('q', '').lower().strip()
    results = []
    # Handle "ward X" format by removing "ward" and trimming
    if query.startswith('ward'):
        query = query[4:].strip()
    for ward_num, ward_info in wards_data.items():
        # For numeric searches, be more precise
        try:
            search_num = query.strip()
            ward_number = ward_num.strip()
            if search_num and ward_number.isdigit():
                # Only match if it's the exact number or starts with the search number
                if ward_number == search_num or ward_number.startswith(search_num):
                    patient_count = len(ward_info.get('patients', {}))
                    results.append({
                        'ward_num': ward_num,
                        'filename': ward_info['filename'],
                        'patient_count': patient_count
                    })
                continue
        except ValueError:
            pass
        # For non-numeric searches, use simple contains
        if (query in ward_num.lower() or 
            query in ward_info['filename'].lower()):
            patient_count = len(ward_info.get('patients', {}))
            results.append({
                'ward_num': ward_num,
                'filename': ward_info['filename'],
                'patient_count': patient_count
            })
    return jsonify(results)

@app.route('/patient/<patient_id>')
@login_required
def patient(patient_id):
    # Get patient from database
    patient = Patient.query.filter_by(hospital_id=patient_id, is_active=True).first_or_404()
    log_access('view_patient', patient_id)
    # Record recently viewed
    try:
        recent_view = RecentlyViewedPatient.query.filter_by(
            user_id=current_user.id,
            patient_id=patient_id
        ).first()
        if not recent_view:
            recent = RecentlyViewedPatient(
                user_id=current_user.id,
                patient_id=patient_id,
                ward_num=patient.current_ward,
                patient_name=patient.name
            )
            db.session.add(recent)
            # Limit to 10 recent patients per user
            older_views = RecentlyViewedPatient.query\
                .filter_by(user_id=current_user.id)\
                .order_by(RecentlyViewedPatient.viewed_at.desc())\
                .offset(10).all()
            for old in older_views:
                db.session.delete(old)
            db.session.commit()
        else:
            recent_view.viewed_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        print(f"Error recording patient view: {str(e)}")
        db.session.rollback()
    # Get all notes for this patient
    notes = Note.query.filter_by(patient_id=patient.id)\
        .order_by(Note.timestamp.desc()).all()
    # Format notes for template
    formatted_notes = []
    for note in notes:
        note_dict = note.to_dict()
        if note.system_user_id:
            user = User.query.get(note.system_user_id)
            note_dict['staff'] = user.username if user else 'Unknown'
        else:
            note_dict['staff'] = note.staff_name
        
        # Add this line to ensure the note content is available with the key 'note'
        note_dict['note'] = note.note_text
        
        formatted_notes.append(note_dict)
    # Format patient info for template
    patient_info_dict = {
        "Patient ID": patient.hospital_id,
        "Name": patient.name,
        "Ward": patient.current_ward,
        "DOB": patient.dob,
    }
    ward = Ward.query.filter_by(ward_number=patient.current_ward).first()
    return render_template('patient.html',
                         patient_id=patient_id,
                         patient_info_dict=patient_info_dict,
                         vitals="",  # This could be added to Patient model if needed
                         care_notes=formatted_notes,
                         ward_num=patient.current_ward,
                         pdf_filename=ward.pdf_file if ward else None,
                         pdf_creation_time=ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward and ward.last_updated else "Unknown",
                         notes_enabled=get_notes_enabled())

@app.route('/pdf/<patient_id>')
@login_required
def serve_patient_pdf(patient_id):
    # Try to find which ward contains this patient
    ward_num_found = None
    for ward_num, ward_info in wards_data.items():
        if ward_info.get("patients") and patient_id in ward_info["patients"]:
            ward_num_found = ward_num
            break
    if not ward_num_found:
        # This is inefficient but necessary if we don't know which ward has the patient
        for ward_num in wards_data:
            load_specific_ward(ward_num)
            if ward_num in wards_data and wards_data[ward_num].get("patients") and patient_id in wards_data[ward_num]["patients"]:
                ward_num_found = ward_num
                break
    if ward_num_found:
        # Log this access
        log_access('view_pdf', patient_id)
        # Get the PDF filename
        pdf_filename = wards_data[ward_num_found]["filename"]
        # Return a response with instructions to create a proper PDF viewer
        return """
        <div style="padding: 20px; font-family: Arial, sans-serif; text-align: center;">
            <h2>PDF Viewer Not Available</h2>
            <p>Individual PDF extraction for patient records is not implemented in this version.</p>
            <p>Patient data is displayed in the main patient view.</p>
        </div>
        """
    return "Patient PDF not found", 404

@app.route('/audit-log')
@login_required
def view_audit_log():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('audit_log.html', logs=logs)

@app.route('/ward_patient_count/<ward_num>')
@login_required
def ward_patient_count(ward_num):
    # URL decode the ward_num to handle special characters
    ward_num = unquote(ward_num)
    # Check if we already have the ward data loaded
    if ward_num in wards_data and wards_data[ward_num].get("patients"):
        count = len(wards_data[ward_num]["patients"])
    else:
        # Load ward data if not already loaded
        load_specific_ward(ward_num)
        if ward_num in wards_data and wards_data[ward_num].get("patients"):
            count = len(wards_data[ward_num]["patients"])
        else:
            count = 0
    return jsonify({"ward": ward_num, "count": count})

@app.route('/recent-patients')
@login_required
def recent_patients():
    # First get all recent views
    all_recents = RecentlyViewedPatient.query\
        .filter_by(user_id=current_user.id)\
        .order_by(RecentlyViewedPatient.viewed_at.desc())\
        .all()
    # Keep track of patient IDs we've seen to avoid duplicates
    seen_patients = set()
    unique_recents = []
    # Only add each patient once (the most recent view)
    for recent in all_recents:
        if recent.patient_id not in seen_patients:
            unique_recents.append(recent)
            seen_patients.add(recent.patient_id)
            # Stop once we have 10 unique patients
            if len(unique_recents) >= 10:
                break
    return jsonify([r.to_dict() for r in unique_recents])

@app.route('/admin/toggle_notes', methods=['POST'])
@login_required
def toggle_notes():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    current_status = get_notes_enabled()
    new_status = not current_status
    Settings.set_setting('notes_enabled', str(new_status).lower())
    status = 'enabled' if new_status else 'disabled'
    flash(f'Note-adding functionality has been {status}', 'success')
    return redirect(request.referrer or url_for('admin_notes'))

# Update the add_care_note route to check if notes are enabled
@app.route('/add_care_note/<patient_id>', methods=['POST'])
@login_required
def add_care_note(patient_id):
    if not get_notes_enabled():
        flash('Note-adding functionality is currently disabled by the administrator', 'note-error')
        return redirect(url_for('patient', patient_id=patient_id))
    try:
        note_text = request.form.get('note')
        if not note_text:
            return jsonify({'error': 'Note text is required'}), 400
        # Find which ward this patient belongs to and get patient name
        ward_id = None
        patient_name = "Unknown"
        for ward_num, ward_info in wards_data.items():
            if ward_info.get("patients") and patient_id in ward_info.get("patients", {}):
                ward_id = ward_num
                patient_name = ward_info["patients"][patient_id].get("name", "Unknown")
                break
        note = CareNote(
            patient_id=patient_id,
            user_id=current_user.id,
            note=note_text,
            ward_id=ward_id,
            patient_name=patient_name  # Save patient name
        )
        # Add and save the care note
        db.session.add(note)
        safe_commit()
        # Record in audit log
        log_access('add_note', patient_id)
        # Use session-based flash instead of regular flash
        session['care_note_success'] = 'Note added successfully!'
        return redirect(url_for('patient', patient_id=patient_id))
    except Exception as e:
        app.logger.error(f'Error adding note: {str(e)}\n{traceback.format_exc()}')
        flash('Error adding note: ' + str(e), 'note-error')
        return jsonify({'error': str(e)}), 500

@app.route('/my_shift_notes')
@login_required
def my_shift_notes():
    show_all = request.args.get('show_all') == '1'
    query = CareNote.query.filter_by(user_id=current_user.id)
    if not show_all:
        # Only apply time filter if not showing all
        cutoff = datetime.utcnow() - timedelta(hours=12)
        query = query.filter(CareNote.timestamp >= cutoff)
    notes = query.order_by(CareNote.timestamp.desc()).all()
    # Prepare notes with names
    notes_with_names = []
    # Pre-load ward display names for efficiency
    ward_display_names = {ward_id: info.get("display_name", ward_id) 
                         for ward_id, info in wards_data.items()}
    for note in notes:
        # Get ward name from our preloaded display names
        ward_name = ward_display_names.get(note.ward_id, note.ward_id)
        # Use stored patient name
        patient_name = note.patient_name or "Unknown"
        notes_with_names.append({
            **note.to_dict(),
            'patient_name': patient_name,
            'ward': ward_name
        })
    return render_template('shift_notes.html', 
                          notes=notes_with_names,
                          show_all=show_all)

@app.route('/admin/notes')
@login_required
def admin_notes():
    # Only admins can access this page
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    # Get filter parameters with explicit empty defaults
    ward_id = request.args.get('ward', '')
    username = request.args.get('username', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    
    # Build query with filters
    query = CareNote.query
    
    # Track whether any filters are applied
    filters_applied = False
    
    # Apply user filter by username
    if username:
        filters_applied = True
        # Get all users matching the username pattern
        matching_users = User.query.filter(User.username.like(f'%{username}%')).all()
        filtered_user_ids = [u.id for u in matching_users]
        if filtered_user_ids:
            query = query.filter(CareNote.user_id.in_(filtered_user_ids))
        else:
            # No matching users, return empty result
            query = query.filter(CareNote.id < 0)
    
    # Apply date filters
    if date_from:
        filters_applied = True
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(CareNote.timestamp >= date_from_obj)
        except ValueError:
            pass
    if date_to:
        filters_applied = True
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)  # Fixed syntax error here
            query = query.filter(CareNote.timestamp <= date_to_obj)
        except ValueError:
            pass
    
    # Apply ward filter - ensure it's a non-empty string
    if ward_id and ward_id.strip():
        filters_applied = True
        query = query.filter(CareNote.ward_id == ward_id)
    
    # Count total matching notes before pagination
    total_notes = query.count()
    # Paginate the query
    paginated_notes = query.order_by(CareNote.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    users_map = {}
    # Get all users from the notes for batch processing
    user_ids = list(set(note.user_id for note in CareNote.query.with_entities(CareNote.user_id).distinct()))
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        users_map = {user.id: user.username for user in users}
    
    # Get ward display names for dropdown
    available_wards = {}
    for ward_id in wards_data.keys():
        # Store the ward info dictionary, not just the display name
        available_wards[ward_id] = wards_data[ward_id]
    
    # Sort wards alphabetically by display name for better UX
    # Fix: the lambda now properly handles both dictionary and string values
    available_wards = dict(sorted(
        available_wards.items(),
        key=lambda item: item[1]["display_name"].lower() if isinstance(item[1], dict) and "display_name" in item[1] else item[0].lower()
    ))
    
    # Get all available usernames for the filter dropdown from notes
    available_usernames = sorted([users_map.get(uid) for uid in user_ids if uid in users_map])
    
    # Preserve the exact ward_id from request parameters
    selected_ward = request.args.get('ward', '')
    
    filters = {
        'ward': selected_ward,
        'username': username,
        'date_from': date_from,
        'date_to': date_to,
        'applied': filters_applied
    }
    
    # Process notes for display
    notes = []
    for note in paginated_notes.items:
        # Get ward name efficiently using our preloaded display names
        # Fix - extract display_name from the ward_info dictionary 
        ward_info = available_wards.get(note.ward_id)
        if isinstance(ward_info, dict) and 'display_name' in ward_info:
            ward_name = ward_info['display_name']
        else:
            ward_name = note.ward_id or "Unknown"
        # Use stored patient name
        patient_name = note.patient_name or "Unknown"
        # Get username from our preloaded map
        username_display = users_map.get(note.user_id, "Unknown")
        notes.append({
            'timestamp': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'patient_id': note.patient_id,
            'patient_name': patient_name,
            'note': note.note,
            'ward': ward_name,
            'username': username_display,
        })
    
    return render_template('admin_notes.html',
                          notes=notes,
                          wards=available_wards,
                          usernames=available_usernames,
                          filters=filters,
                          page=page,
                          pages=paginated_notes.pages,
                          total_notes=total_notes,
                          prev_page=paginated_notes.prev_num or page,
                          next_page=paginated_notes.next_num or page,
                          excel_export_available=EXCEL_EXPORT_AVAILABLE,
                          notes_enabled=get_notes_enabled(),
                          timeout_enabled=get_timeout_enabled(),
                          timeout_minutes=get_timeout_minutes())

@app.route('/admin/notes/export/<format>')
@login_required
def export_notes(format):
    # Only admins can access this feature
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get filter parameters with explicit empty defaults
    ward_id = request.args.get('ward', '')
    username = request.args.get('username', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query with filters
    query = CareNote.query
    
    # Apply user filter by username
    if username:
        matching_users = User.query.filter(User.username.like(f'%{username}%')).all()
        filtered_user_ids = [u.id for u in matching_users]
        if filtered_user_ids:
            query = query.filter(CareNote.user_id.in_(filtered_user_ids))
        else:
            query = query.filter(CareNote.id < 0)
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(CareNote.timestamp >= date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)  # Fixed syntax error here
            query = query.filter(CareNote.timestamp <= date_to_obj)
        except ValueError:
            pass
    
    # Apply ward filter - ensure it's a non-empty string
    if ward_id and ward_id.strip():
        query = query.filter(CareNote.ward_id == ward_id)
    
    # Get the filtered notes
    notes = query.order_by(CareNote.timestamp.desc()).all()
    
    # Pre-load all users for efficiency
    user_ids = list(set(note.user_id for note in notes))
    users = User.query.filter(User.id.in_(user_ids)).all()
    users_map = {user.id: user.username for user in users}
    
    # Pre-load ward display names
    ward_display_names = {ward_id: info.get("display_name", ward_id) 
                          for ward_id, info in wards_data.items()}
    
    # Process notes efficiently
    export_data = []
    for note in notes:
        ward_name = ward_display_names.get(note.ward_id, "Unknown")
        username = users_map.get(note.user_id, "Unknown")
        export_data.append({
            'timestamp': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'patient_id': note.patient_id,
            'patient_name': note.patient_name or "Unknown",
            'note': note.note,
            'ward': ward_name,
            'username': username
        })
    
    if format == 'excel':
        if not EXCEL_EXPORT_AVAILABLE:
            error_msg = "Excel export is not available. Please ensure xlsxwriter package is installed."
            print(error_msg)  # Log to server console
            flash(error_msg, 'error')
            return redirect(url_for('admin_notes'))
        return export_excel(export_data)
    elif format == 'pdf':
        return export_pdf(export_data)
    else:
        flash('Unsupported export format')
        return redirect(url_for('admin_notes'))

def export_excel(data):
    """Export data to Excel with robust error handling for web deployment"""
    try:
        # Create an in-memory output file
        output = io.BytesIO()
        # Create a workbook and add a worksheet
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Notes')
        
        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})
        
        # Write headers
        headers = ['Timestamp', 'Ward', 'Patient Name', 'Patient ID', 'User', 'Note']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)
        
        # Write data rows
        for row, item in enumerate(data, start=1):
            worksheet.write(row, 0, item['timestamp'])
            worksheet.write(row, 1, item['ward'])
            worksheet.write(row, 2, item['patient_name'])
            worksheet.write(row, 3, item['patient_id'])
            worksheet.write(row, 4, item['username'])
            worksheet.write(row, 5, item['note'])
        
        # Auto-filter and auto-width columns
        worksheet.autofilter(0, 0, len(data), len(headers) - 1)
        worksheet.set_column(0, 0, 18)  # Timestamp
        worksheet.set_column(1, 1, 15)  # Ward
        worksheet.set_column(2, 2, 20)  # Patient Name
        worksheet.set_column(3, 3, 15)  # Patient ID
        worksheet.set_column(4, 4, 15)  # Username
        worksheet.set_column(5, 5, 50)  # Note
        
        workbook.close()
        output.seek(0)
        
        # Generate filename with current date
        filename = f"notes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"Excel export failed: {str(e)}")  # Detailed server-side logging
        flash(f"Excel export failed: {str(e)}", "error")
        return redirect(url_for('admin_notes'))

def export_pdf(data):
    """Export data to PDF with robust error handling for web deployment"""
    try:
        # Create an in-memory output file
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Add minimal header
        elements.append(Paragraph(f"Notes Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Heading2"]))
        elements.append(Spacer(1, 12))
        
        # Create table with optimized data
        table_data = [["Time", "Ward", "Patient", "User", "Note"]]
        
        # Process data in chunks to reduce memory usage
        chunk_size = 100
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            for item in chunk:
                patient_info = f"{item['patient_name']}\n{item['patient_id']}"
                # Pre-process note text to reduce Paragraph creation overhead
                note_text = Paragraph(item['note'].replace('\n', '<br/>'), styles['Normal'])
                table_data.append([
                    item['timestamp'].split()[1],  # Only show time to save space
                    item['ward'],
                    patient_info,
                    item['username'],
                    note_text
                ])
        
        table = Table(table_data, colWidths=[50, 50, 80, 60, 280])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT')
        ]))
        elements.append(table)
        doc.build(elements)
        output.seek(0)
        
        # Generate filename with current date
        filename = f"notes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"PDF export failed: {str(e)}")  # Detailed server-side logging
        flash(f"PDF export failed: {str(e)}", "error")
        return redirect(url_for('admin_notes'))

@app.before_request
def store_referrer():
    """Store referrer for better navigation"""
    if request.endpoint and 'static' not in request.endpoint and request.method == 'GET':
        excluded_endpoints = ['logout', 'login', 'serve_static']
        if request.endpoint not in excluded_endpoints:
            session['last_page'] = request.url

@app.before_request
def check_session_timeout():
    """Improved session timeout check"""
    if current_user.is_authenticated and request.endpoint not in ['static', 'logout']:
        if get_timeout_enabled():
            try:
                last_active = session.get('last_active')
                if last_active is None:
                    session['last_active'] = datetime.utcnow().timestamp()
                    return
                
                timeout_minutes = get_timeout_minutes()
                last_active_dt = datetime.fromtimestamp(float(last_active))
                time_diff = datetime.utcnow() - last_active_dt
                
                if time_diff > timedelta(minutes=timeout_minutes):
                    logout_user()
                    flash('Your session has expired due to inactivity')
                    return redirect(url_for('login'))
                
                session['last_active'] = datetime.utcnow().timestamp()
            except Exception as e:
                print(f"Session timeout error: {str(e)}")
                session['last_active'] = datetime.utcnow().timestamp()

@app.route('/admin/timeout_settings', methods=['POST'])
@login_required
def update_timeout_settings():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    enabled = request.form.get('timeout_enabled') == '1'
    minutes_str = request.form.get('timeout_minutes', '')
    
    if not minutes_str.isdigit():
        flash('Timeout must be a positive number', 'error')
        return redirect(url_for('admin_notes'))
    
    minutes = int(minutes_str)
    if minutes < 1 or minutes > 1440:  # 1440 minutes = 24 hours
        flash('Timeout must be between 1 and 1440 minutes', 'error')
        return redirect(url_for('admin_notes'))
    
    Settings.set_setting('timeout_enabled', str(enabled).lower())
    Settings.set_setting('timeout_minutes', str(minutes))
    flash('Session timeout settings updated successfully', 'success')
    return redirect(url_for('admin_notes'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database (creates tables if missing)."""
    db.create_all()
    click.echo('Database initialized.')

app.cli.add_command(init_db_command)

setup_logger(app)

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()  # Roll back any failed database sessions
    error_details = traceback.format_exc()
    app.logger.error(f'Server Error: {error_details}')
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the full stack trace
    app.logger.error(f'Unhandled Exception: {str(e)}\n{traceback.format_exc()}')
    # Roll back any failed database sessions
    if db.session:
        db.session.rollback()
    return render_template('500.html'), 500

# Enhance database error handling in our routes
def safe_commit():
    """Safely commit database changes with error logging"""
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Database Error: {str(e)}\n{traceback.format_exc()}')
        raise

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        db.create_all(bind=['audit'])
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
        # Create test user if not exists
        if not User.query.filter_by(username='nurse1').first():
            test_user = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(test_user)
        db.session.commit()
    for port in range(5000, 5011):  # Try ports 5000-5010 until we find an available one
        try:
            app.run(host='0.0.0.0', port=port, debug=True)
            break
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"Port {port} is in use, trying next port...")
                continue
            else:
                raise  # Re-raise other exceptions