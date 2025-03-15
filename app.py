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

    def to_dict(self):
        # Include user_id so we can fetch the staff member name later.
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'note': self.note,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id
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

def extract_patient_info(pdf_path):
    patient_data = {}
    try:
        reader = PdfReader(pdf_path)
        
        # Process each page as a potential patient record
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            lines = text.split('\n')
            
            # Initialize patient info for this page
            patient_id = None
            patient_name = None
            patient_ward = None
            patient_dob = None
            care_notes = []
            
            # This flag will help us know what the next line contains
            expecting_value = None
            in_care_notes = False
            care_notes_section_start = -1
            
            # Process each line
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check for the page title (start of a patient record)
                if line.startswith("Patient Record - Ward"):
                    # Reset for new patient
                    expecting_value = None
                    in_care_notes = False
                    continue
                
                # Check if we're in the care notes section
                if line == "Continuous Care Notes":
                    in_care_notes = True
                    care_notes_section_start = i
                    continue
                    
                # If we're expecting a specific value...
                if expecting_value:
                    if expecting_value == "Patient ID":
                        patient_id = line
                    elif expecting_value == "Name":
                        patient_name = line
                    elif expecting_value == "Ward":
                        patient_ward = line
                    elif expecting_value == "DOB":
                        patient_dob = line
                    
                    expecting_value = None
                    continue
                
                # Check for field labels
                if line == "Patient ID:":
                    expecting_value = "Patient ID"
                elif line == "Name:":
                    expecting_value = "Name"
                elif line == "Ward:":
                    expecting_value = "Ward"
                elif line == "DOB:":
                    expecting_value = "DOB"
            
            # Process care notes - we need special handling for the care notes section
            if in_care_notes and care_notes_section_start > 0:
                # Find the header row
                header_row_idx = -1
                for i in range(care_notes_section_start + 1, len(lines)):
                    if lines[i].strip() == "Date & Time":
                        header_row_idx = i
                        break
                
                if header_row_idx > 0:
                    # We should have the header row and the next two rows are "Staff Member" and "Notes"
                    # After that, the actual data starts in groups of 3 lines (date, staff, note)
                    data_start_idx = header_row_idx + 3
                    
                    # Process care notes in groups of 3 lines
                    i = data_start_idx
                    while i < len(lines) - 2:
                        date_line = lines[i].strip()
                        staff_line = lines[i + 1].strip()
                        note_line = lines[i + 2].strip()
                        
                        if date_line and staff_line:  # Ensure we have at least date and staff
                            care_notes.append({
                                "date": date_line,
                                "staff": staff_line,
                                "note": note_line
                            })
                        
                        i += 3  # Move to next group of 3 lines
            
            # If we found a patient ID and name, add to our data
            if patient_id and patient_name:
                patient_info = {
                    "Name": patient_name,
                    "Ward": patient_ward,
                    "DOB": patient_dob
                }
                
                # Filter out None values
                patient_info = {k: v for k, v in patient_info.items() if v is not None}
                
                patient_data[patient_id] = {
                    "info": patient_info,
                    "name": patient_name,
                    "vitals": "",
                    "care_notes": care_notes
                }
        
        return patient_data
    
    except Exception as e:
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
    
    # First create the ward data without sorting
    for pdf_filename in ward_files:
        ward_num = pdf_filename.split('_')[1]
        display_name = ward_num  # Default display name (for named wards)
        
        # For numeric ward names, prepend "Ward " to match UI display
        if ward_num.isdigit():
            display_name = f"Ward {ward_num}"
            
        wards_meta[ward_num] = {
            "filename": pdf_filename,
            "display_name": display_name,
            "patients": {}  # Empty placeholder, will be filled on demand
        }
    
    # Now sort the wards based on their display names
    sorted_ward_nums = sorted(wards_meta.keys(), 
                             key=lambda x: wards_meta[x]["display_name"].lower())
    
    # Create a new ordered dictionary with sorted ward data
    sorted_wards_meta = {}
    for ward_num in sorted_ward_nums:
        sorted_wards_meta[ward_num] = wards_meta[ward_num]
    
    return sorted_wards_meta

# Process a single ward PDF, with caching
@lru_cache(maxsize=100)  # Cache more ward data
def process_ward_pdf(pdf_filename):
    if os.path.exists(pdf_filename):
        patient_info = extract_patient_info(pdf_filename)
        return patient_info
    return {}

# Load a specific ward's data
def load_specific_ward(ward_num):
    global wards_data
    
    # Try to clear any potentially cached data for problematic wards
    if ward_num in wards_data and not wards_data[ward_num].get("patients"):
        # Force clear the cache for this specific ward
        process_ward_pdf.cache_clear()
    
    if ward_num in wards_data and wards_data[ward_num].get("patients"):
        # Data already loaded
        return
    
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
    if request.method == 'POST':
        default_ward = request.form.get('default_ward')
        
        # Update user's default ward
        current_user.default_ward = default_ward
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Sort wards alphabetically by display_name for the dropdown
    sorted_wards = {}
    for ward_id, info in sorted(wards_data.items(), key=lambda x: x[1]['display_name'].lower()):
        sorted_wards[ward_id] = info
    
    return render_template('profile.html', wards=sorted_wards, current_ward=current_user.default_ward)

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
        return render_template('ward.html', 
                               ward_num=ward_num,
                               ward_data=ward_info,
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
            if patient_id in wards_data[ward_num]["patients"]:
                ward_num_found = ward_num
                break
    if ward_num_found:
        patient_data = wards_data[ward_num_found]["patients"][patient_id]
        log_access('view_patient', patient_id)
        # Add recently viewed record
        recent = RecentlyViewedPatient(
            user_id=current_user.id,
            patient_id=patient_id,
            ward_num=ward_num_found,
            patient_name=patient_data["name"]
        )
        db.session.add(recent)
        older_views = RecentlyViewedPatient.query.filter_by(user_id=current_user.id)\
            .order_by(RecentlyViewedPatient.viewed_at.desc())\
            .offset(10).all()
        for old in older_views:
            db.session.delete(old)
        db.session.commit()

        # Get PDF care notes from snapshot
        pdf_notes = patient_data.get("care_notes", [])
        # Get new notes from the database
        db_notes = [n.to_dict() for n in CareNote.query.filter_by(patient_id=patient_id).all()]
        for note in db_notes:
            user = User.query.get(note['user_id'])
            note['staff'] = user.username if user else 'Unknown'
            note['is_new'] = True
        # Combine and sort notes (newest first)
        combined = pdf_notes + db_notes
        # Use "timestamp" if available; otherwise use "date" from PDF notes
        combined.sort(key=lambda n: n.get('timestamp') or n.get('date', ''), reverse=True)
        
        # Also get PDF file creation time
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
        
        note = CareNote(
            patient_id=patient_id,
            user_id=current_user.id,
            note=note_text
        )
        
        # Add and save the care note
        db.session.add(note)
        db.session.commit()
        
        # Add audit log entry
        audit_log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,  
            action='add_note',
            patient_id=patient_id
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Use session-based flash instead of regular flash
        session['care_note_success'] = 'Note added successfully!'
        return redirect(url_for('patient', patient_id=patient_id))
    except Exception as e:
        db.session.rollback()
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
    
    # Get patient names for the notes
    notes_with_names = []
    for note in notes:
        patient_name = "Unknown"
        ward_num = None
        
        # Find patient info
        for ward in wards_data.values():
            if ward.get("patients") and note.patient_id in ward["patients"]:
                patient_name = ward["patients"][note.patient_id]["name"]
                ward_num = ward.get("display_name")
                break
        
        notes_with_names.append({
            **note.to_dict(),
            'patient_name': patient_name,
            'ward': ward_num
        })
            
    return render_template('shift_notes.html', notes=notes_with_names)

@app.cli.command('init-carenotes')
def init_carenotes():
    """Initialize the care notes table."""
    with app.app_context():
        db.create_all()  # This will create any missing tables        
        print("Care notes table created successfully.")

@app.cli.command('create-carenotes')
def create_carenotes():
    """Create the care notes table."""
    db.create_all()    
    click.echo('Care notes table has been created.')

def init_db():
    with app.app_context():
        db.create_all()

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
        
        # Check if default_ward column exists in user table
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        if 'default_ward' not in columns:
            db.engine.execute('ALTER TABLE user ADD COLUMN default_ward VARCHAR(50)')
        
        # Create both databases and tables
        db.create_all()
        db.create_all(bind=['audit'])
        
        # Add default_ward column if it doesn't exist
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        if 'default_ward' not in columns:
            db.engine.execute('ALTER TABLE user ADD COLUMN default_ward VARCHAR(50)')
        
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
                raise  # Re-raise other OSErrors
