from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response
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
from flask import (Flask, render_template, request, jsonify, redirect, 
                  url_for, flash, session, make_response, send_file)
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-8712'  # Change this in production
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session lasts 24 hours
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Main database for users
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_BINDS'] = {
    'audit': 'sqlite:///audit.db'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize login manager with improved configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.session_protection = "strong"

# User Model in main database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    default_ward = db.Column(db.String(50), nullable=True)

# Audit Log Model in separate database
class AuditLog(db.Model):
    __bind_key__ = 'audit'  # This tells SQLAlchemy to use the audit database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)  # Store username directly for persistence
    action = db.Column(db.String(50), nullable=False)
    patient_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class RecentlyViewedPatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.String(50), nullable=False)
    ward_num = db.Column(db.String(50), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'patient_id': self.patient_id,
            'ward_num': self.ward_num,
            'patient_name': self.patient_name,
            'viewed_at': self.viewed_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class CareNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ward_id = db.Column(db.String(50), nullable=True)
    patient_name = db.Column(db.String(100), nullable=True)  # Add patient name column

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'note': self.note,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id,
            'ward_id': self.ward_id,
            'patient_name': self.patient_name
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def log_access(action, patient_id=None):
    if current_user.is_authenticated:
        log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,  # Store username directly
            action=action,
            patient_id=patient_id
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
                        current_patient["info"]["Name"] = current_patient["name"]
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
                    care_notes_text = ""
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
                                    "note": note,
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
                    "DOB:": "DOB"
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
            "vitals": "",  # No vitals in the current PDF format
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
    sorted_ward_nums = sorted(wards_meta.keys(), 
                            key=lambda x: wards_meta[x]["display_name"].lower())
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

# Initialize with metadata
init_ward_data()

# Add this function to properly load ward patients data
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)  # Enable remember me
            session.permanent = True  # Use permanent session
            next_page = request.args.get('next')
            log_access('login')
            # Only redirect to 'next' if it's a relative path (security measure)
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page or url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.after_request
def after_request(response):
    # Ensure we have proper security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.route('/logout')
@login_required
def logout():
    log_access('logout')
    # Clear any existing flash messages before logging out
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
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
    # URL decode ward_num and load data
    ward_num = unquote(ward_num)
    load_specific_ward(ward_num)
    if ward_num in wards_data:
        ward_info = wards_data[ward_num]
        log_access('view_ward', f'Ward {ward_num}')
        # Get PDF creation (modification) time
        import os
        pdf_mtime = os.path.getmtime(ward_info["filename"])
        pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
        patient_list = []
        if ward_info.get("patients"):
            # Create a simple list of patients for the template
            for pid, data in ward_info["patients"].items():
                patient_list.append({
                    "id": pid, 
                    "name": data.get("name", "Unknown")
                })
        return render_template('ward.html', 
                              ward_num=ward_num,
                              ward_data={"patients": ward_info.get("patients", {})},
                              pdf_filename=ward_info["filename"],
                              pdf_creation_time=pdf_creation_time)
    return "Ward not found", 404
    
@app.route('/search/<ward_num>')
@login_required
def search(ward_num):
    # URL decode the ward_num to handle special characters
    ward_num = unquote(ward_num)
    # Load this specific ward's data on demand
    load_specific_ward(ward_num)
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
    # Find ward for this patient
    ward_num_found = None
    for ward_num, ward_info in wards_data.items():
        if ward_info.get("patients") and patient_id in ward_info["patients"]:
            ward_num_found = ward_num
            break
    if not ward_num_found:
        for ward_num in wards_data:
            load_specific_ward(ward_num)
            if ward_num in wards_data and wards_data[ward_num]["patients"] and patient_id in wards_data[ward_num]["patients"]:
                ward_num_found = ward_num
                break
    if ward_num_found:
        patient_data = wards_data[ward_num_found]["patients"][patient_id]
        log_access('view_patient', patient_id)
        # Add recently viewed record - but limit to prevent database bloat
        try:
            # Check if patient was recently viewed to avoid duplicate entries
            recent_view = RecentlyViewedPatient.query.filter_by(
                user_id=current_user.id, 
                patient_id=patient_id
            ).first()
            if not recent_view:
                recent = RecentlyViewedPatient(
                    user_id=current_user.id,
                    patient_id=patient_id,
                    ward_num=ward_num_found,
                    patient_name=patient_data["name"]
                )
                db.session.add(recent)
                # Limit to 10 recent patients per user
                older_views = RecentlyViewedPatient.query.filter_by(user_id=current_user.id)\
                    .order_by(RecentlyViewedPatient.viewed_at.desc())\
                    .offset(10).all()
                for old in older_views:
                    db.session.delete(old)
                db.session.commit()
            else:
                # Update timestamp for existing view
                recent_view.viewed_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            # Log but don't fail the request if recording view history fails
            print(f"Error recording patient view: {str(e)}")
            db.session.rollback()
        # Get all PDF notes (no pagination)
        pdf_notes = patient_data.get("care_notes", [])
        # Get new notes from the database
        db_notes = [n.to_dict() for n in CareNote.query.filter_by(patient_id=patient_id)
                   .order_by(CareNote.timestamp.desc()).all()]
        for note in db_notes:
            user = User.query.get(note['user_id'])
            note['staff'] = user.username if user else 'Unknown'
            note['is_new'] = True
        # Combine and sort notes (newest first)
        combined = pdf_notes + db_notes
        combined.sort(key=lambda n: n.get('timestamp') or n.get('date', ''), reverse=True)
        # Get PDF file creation time
        import os
        ward_info = wards_data[ward_num_found]
        pdf_mtime = os.path.getmtime(ward_info["filename"])
        pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if 'care_note_success' in session:
            flash(session.pop('care_note_success'), 'success')
        return render_template('patient.html',
                               patient_id=patient_id,
                               patient_info_dict=patient_data["info"],
                               vitals=patient_data.get("vitals", ""),
                               care_notes=combined,
                               ward_num=ward_num_found,
                               pdf_filename=ward_info["filename"],
                               pdf_creation_time=pdf_creation_time)
    return "Patient not found", 404
    
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
    
from flask_wtf.csrf import validate_csrf

@app.route('/add_care_note/<patient_id>', methods=['POST'])
@login_required
def add_care_note(patient_id):
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
        db.session.commit()
        flash('Note added successfully!', 'note-success')
        # Use session-based flash instead of regular flash
        session['care_note_success'] = 'Note added successfully!'
        return redirect(url_for('patient', patient_id=patient_id))
    except Exception as e:
        db.session.rollback()
        flash('Error adding note: ' + str(e), 'note-error')
        return jsonify({'error': str(e)}), 500

@app.route('/my_shift_notes')
@login_required
def my_shift_notes():
    # Get notes from last 12 hours
    cutoff = datetime.utcnow() - timedelta(hours=12)
    notes = CareNote.query\
        .filter(CareNote.user_id == current_user.id)\
        .filter(CareNote.timestamp >= cutoff)\
        .order_by(CareNote.timestamp.desc())\
        .all()
    
    # Prepare notes with names - now using stored patient_name
    notes_with_names = []
    
    # Pre-load ward display names for efficiency
    ward_display_names = {ward_id: info.get("display_name", ward_id) 
                         for ward_id, info in wards_data.items()}
    
    for note in notes:
        # Get ward name from our preloaded display names
        ward_name = "Unknown"
        if note.ward_id:
            ward_name = ward_display_names.get(note.ward_id, note.ward_id)
        
        # Use stored patient_name
        patient_name = note.patient_name or "Unknown"
        
        notes_with_names.append({
            **note.to_dict(),
            'patient_name': patient_name,
            'ward': ward_name
        })
    
    return render_template('shift_notes.html', notes=notes_with_names)

@app.route('/admin/notes')
@login_required
def admin_notes():
    # Only admins can access this page
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get filter parameters
    ward_id = request.args.get('ward')
    username = request.args.get('username')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)
    
    # Check if this is a reset request
    if request.args.get('reset') == '1':
        return redirect(url_for('admin_notes'))
    
    # Build query with filters
    query = CareNote.query
    
    # Track whether any filters are applied
    filters_applied = False
    
    if username:
        filters_applied = True
        user_ids = [u.id for u in User.query.filter(User.username.like(f'%{username}%')).all()]
        if user_ids:
            query = query.filter(CareNote.user_id.in_(user_ids))
        else:
            # No matching users, return empty result
            query = query.filter(CareNote.id < 0)
    
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
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(CareNote.timestamp <= date_to_obj)
        except ValueError:
            pass
    
    # Ward filtering using ward_id field
    if ward_id:
        filters_applied = True
        query = query.filter(CareNote.ward_id == ward_id)
    
    # Count total matching notes before pagination
    total_notes = query.count()
    
    # Paginate the query
    paginated_notes = query.order_by(CareNote.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get all user IDs from this page for batch processing
    user_ids = list(set(note.user_id for note in paginated_notes.items))
    # Get usernames in a single database query
    users_map = {}
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        users_map = {user.id: user.username for user in users}
    
    # For ward info, we'll only load data for wards that appear in these notes
    ward_ids = list(set(note.ward_id for note in paginated_notes.items if note.ward_id))
    # Preload ward display names to avoid looking up repeatedly
    ward_display_names = {}
    for ward_id in ward_ids:
        if ward_id in wards_data:
            ward_display_names[ward_id] = wards_data[ward_id].get("display_name", ward_id)
    
    # Process notes with minimal database and ward data loading
    notes = []
    for note in paginated_notes.items:
        # Get ward name efficiently using our preloaded display names
        ward_name = "Unknown"
        if note.ward_id:
            ward_name = ward_display_names.get(note.ward_id, note.ward_id)
        
        # Use stored patient name - no need to load ward data
        patient_name = note.patient_name or "Unknown"
        
        # Get username from our preloaded map
        username = users_map.get(note.user_id, "Unknown")
        
        notes.append({
            'timestamp': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'patient_id': note.patient_id,
            'patient_name': patient_name,
            'note': note.note,
            'ward': ward_name,
            'username': username
        })
    
    # Get all available wards for the filter dropdown
    wards = get_ward_metadata()
    # Get all usernames for the filter dropdown - use a direct query
    usernames = [u.username for u in User.query.with_entities(User.username)]
    
    return render_template('admin_notes.html',
                          notes=notes,
                          wards=wards,
                          usernames=usernames,
                          filters={
                              'ward': ward_id,
                              'username': username,
                              'date_from': date_from,
                              'date_to': date_to,
                              'applied': filters_applied
                          },
                          page=page,
                          pages=paginated_notes.pages,
                          total_notes=total_notes,
                          prev_page=paginated_notes.prev_num or page,
                          next_page=paginated_notes.next_num or page,
                          excel_export_available=EXCEL_EXPORT_AVAILABLE)

@app.route('/admin/notes/export/<format>')
@login_required
def export_notes(format):
    # Only admins can access this feature
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    if format == 'excel' and not EXCEL_EXPORT_AVAILABLE:
        flash('Excel export is not available. Please install xlsxwriter package.', 'error')
        return redirect(url_for('admin_notes'))
    
    # Get filter parameters
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    ward_id = request.args.get('ward_id', '')
    user_id = request.args.get('user_id', '')
    
    # Start with base query
    query = CareNote.query
    
    # Apply date filters
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        query = query.filter(CareNote.timestamp >= start_date)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Add one day to include the entire end date
        end_date = end_date + timedelta(days=1)
        query = query.filter(CareNote.timestamp <= end_date)
    
    # Apply user filter
    if user_id:
        query = query.filter(CareNote.user_id == user_id)
    
    # Get all notes
    all_notes = query.order_by(desc(CareNote.timestamp)).all()
    
    # Filter by ward if needed and collect all data
    export_data = []
    
    # Pre-load all ward data to avoid repeatedly loading it
    for ward_num in wards_data.keys():
        load_ward_patients(ward_num)
    
    for note in all_notes:
        # Get patient name and ward
        patient_name = "Unknown"
        ward_name = "Unknown"
        patient_ward = None
        
        # Find patient info in loaded wards
        for ward_num, ward_info in wards_data.items():
            if ward_info.get("patients") and note.patient_id in ward_info.get("patients", {}):
                patient_name = ward_info["patients"][note.patient_id].get("name", "Unknown")
                patient_ward = ward_num
                ward_name = ward_info.get("display_name", ward_num)
                break
        
        # If we have a ward filter, skip this note if it doesn't match
        if ward_id and patient_ward != ward_id:
            continue
        
        # Get username
        user = User.query.get(note.user_id)
        username = user.username if user else "Unknown"
        
        export_data.append({
            'timestamp': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'patient_id': note.patient_id,
            'patient_name': patient_name,
            'note': note.note,
            'ward': ward_name,
            'username': username
        })
    
    # Generate appropriate export format
    if format == 'excel':
        if not EXCEL_EXPORT_AVAILABLE:
            flash('Excel export is not available on this server. Please contact the administrator.', 'error')
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
        # Log the error
        print(f"Excel export failed: {str(e)}")
        flash(f"Excel export failed: {str(e)}", "error")
        return redirect(url_for('admin_notes'))

def export_pdf(data):
    # Create an in-memory output file
    output = io.BytesIO()
    
    # Create a PDF document
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    normal_style = styles["Normal"]
    
    # Create note style with proper wrapping
    note_style = ParagraphStyle(
        'NoteStyle',
        parent=styles['Normal'],
        spaceBefore=1,
        spaceAfter=1,
        leftIndent=0,
        rightIndent=0,
    )
    
    # Add title
    elements.append(Paragraph("Notes Export", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    elements.append(Spacer(1, 12))
    
    # Prepare table data
    table_data = [["Timestamp", "Ward", "Patient", "User", "Note"]]
    for item in data:
        patient_info = f"{item['patient_name']}\nID: {item['patient_id']}"
        note_text = Paragraph(item['note'].replace('\n', '<br/>'), note_style)
        table_data.append([
            item['timestamp'],
            item['ward'],
            patient_info,
            item['username'],
            note_text
        ])
    
    # Create the table
    table = Table(table_data, colWidths=[80, 60, 100, 60, 220])
    
    # Style the table
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    elements.append(table)
    
    # Build the PDF
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

@app.cli.command('init-carenotes')
def init_carenotes():
    """Initialize the care notes table."""
    with app.app_context():
        db.create_all()  # This will create any missing tables
        print("Care notes table created successfully.")

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database (creates tables if missing)."""
    db.create_all()
    click.echo('Database initialized.')

app.cli.add_command(init_db_command)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Check if columns exist and add if needed
        inspector = db.inspect(db.engine)
        
        # Add default_ward column to User if needed
        user_columns = [col['name'] for col in inspector.get_columns('user')]
        if 'default_ward' not in user_columns:
            db.engine.execute('ALTER TABLE user ADD COLUMN default_ward VARCHAR(50)')
        
        # Add ward_id column to CareNote if needed
        carenote_columns = [col['name'] for col in inspector.get_columns('care_note')]
        if 'ward_id' not in carenote_columns:
            db.engine.execute('ALTER TABLE care_note ADD COLUMN ward_id VARCHAR(50)')
            
        # Add patient_name column to CareNote if needed
        if 'patient_name' not in carenote_columns:
            db.engine.execute('ALTER TABLE care_note ADD COLUMN patient_name VARCHAR(100)')
        
        # Create both databases and tables
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
    
    # Try ports 5000-5010 until we find an available one
    for port in range(5000, 5011):
        try:
            app.run(host='0.0.0.0', port=port, debug=True)
            break
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"Port {port} is in use, trying next port...")
                continue
            else:
                raise  # Re-raise other exceptions