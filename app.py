from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
    Settings, get_notes_enabled, get_timeout_enabled, get_timeout_minutes,
    CareNote, RecentlyViewedPatient, NoteTemplate, TemplateCategory  # Add these missing imports
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
    'audit': 'sqlite:///audit.db',
    'pdf_parsed': 'sqlite:///pdf_parsed.db'  # Add pdf_parsed database binding
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

# Remove extract_patient_info function - data should come from database
# Also remove process_patient_data since it was only used by extract_patient_info
# Keep other functions intact

@lru_cache(maxsize=2)
def process_ward_pdf(pdf_filename):
    """Deprecated: Data should come from database initialization"""
    return {}

# Replace PDF-based ward metadata loading with database-only version
def get_ward_metadata():
    """Get ward metadata directly from database"""
    # Query all wards and sort them appropriately
    return Ward.query.order_by(
        # Sort numeric wards first, then by number/name
        db.case([
            (Ward.ward_number.regexp_match('^\d+$'), 0)
        ], else_=1),
        # For numeric wards, sort by integer value
        db.case([
            (Ward.ward_number.regexp_match('^\d+$'), 
             db.cast(Ward.ward_number, db.Integer))
        ], else_=0),
        Ward.ward_number
    ).all()

# Load a specific ward's data
def load_specific_ward(ward_num):
    """Get ward and patient data directly from database"""
    try:
        # Get ward data
        ward = Ward.query.filter_by(ward_number=ward_num).first()
        if not ward:
            return None
            
        # Get all active patients in ward
        patients = Patient.query.filter_by(
            current_ward=ward_num,
            is_active=True
        ).order_by(Patient.name).all()
        
        return {
            'ward': ward,
            'patients': patients
        }
        
    except Exception as e:
        print(f"Error loading ward {ward_num}: {str(e)}")
        return None

def init_ward_data():
    """Initialize ward data ensuring database is ready"""
    try:
        # Verify database connectivity and ward table exists
        Ward.query.first()
        print("Ward data initialization complete - database ready")
    except Exception as e:
        print(f"Error initializing ward data: {str(e)}")
        # Let the error propagate to trigger app startup failure if DB is not ready
        raise

# Replace the load_ward_patients function with the following:

def load_ward_patients(ward_num):
    """Load patient data from database for a specific ward."""
    try:
        # Query the ward record from the database
        ward = Ward.query.filter_by(ward_number=ward_num).first()
        if not ward:
            print(f"Ward {ward_num} not found in database")
            return None
        # Query patients from the database
        patients = Patient.query.filter_by(current_ward=ward_num, is_active=True).order_by(Patient.name).all()
        patient_data = {}
        for patient in patients:
            patient_data[patient.hospital_id] = {
                "name": patient.name,
                "info": {
                    "DOB": patient.dob,
                    "Ward": ward_num
                }
            }
        # Return a dictionary with ward info and patients data
        return {
            "ward": ward,
            "patients": patient_data
        }
    except Exception as e:
        print(f"Error loading patients for ward {ward_num}: {str(e)}")
        return None

# Update load_specific_ward to use the new function
def load_specific_ward(ward_num):
    """Load a specific ward's data (wrapper around load_ward_patients)"""
    return load_ward_patients(ward_num)

# Add a new function to get patient information efficiently
def get_patient_info_from_ward_data(patient_id, ward_id=None):
    """Get patient info directly from database"""
    if ward_id:
        # Try specific ward first if provided
        patient = Patient.query.filter_by(
            hospital_id=patient_id,
            current_ward=ward_id,
            is_active=True
        ).first()
        
        if patient:
            ward = Ward.query.filter_by(ward_number=ward_id).first()
            return (
                patient.name,
                ward.display_name if ward else ward_id,
                ward_id
            )

    # Try recent ward history
    recent_views = RecentlyViewedPatient.query.filter_by(
        user_id=current_user.id,
        patient_id=patient_id
    ).order_by(RecentlyViewedPatient.viewed_at.desc()).first()

    if recent_views:
        # Verify patient is still in this ward
        patient = Patient.query.filter_by(
            hospital_id=patient_id,
            current_ward=recent_views.ward_num,
            is_active=True
        ).first()
        if patient:
            ward = Ward.query.filter_by(ward_number=recent_views.ward_num).first()
            return (
                patient.name,
                ward.display_name if ward else recent_views.ward_num,
                recent_views.ward_num
            )

    # Fall back to searching all wards
    patient = Patient.query.filter_by(
        hospital_id=patient_id,
        is_active=True
    ).first()
    
    if patient:
        ward = Ward.query.filter_by(ward_number=patient.current_ward).first()
        return (
            patient.name,
            ward.display_name if ward else patient.current_ward,
            patient.current_ward
        )

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
            # Fixed syntax error in f-string with proper curly braces
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
    """Modified index route to load wards directly from database"""
    print(f"Index accessed by: {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    
    # Get show_all parameter
    show_all = request.args.get('show_all') == '1'
    
    # If user has default ward and not showing all, redirect to ward
    if current_user.default_ward and not show_all:
        return redirect(url_for('ward', ward_num=current_user.default_ward))
    
    # Get wards from database
    wards = {}
    ward_records = Ward.query.order_by(Ward.display_name).all()
    
    for ward in ward_records:
        wards[ward.ward_number] = {
            'display_name': ward.display_name,
            'filename': 'Database Record'
        }
    
    return render_template('index.html', wards=wards, show_all=show_all)

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
    """Display a ward's patients using database records only"""
    # URL decode the ward_num to handle special characters
    ward_num = unquote(ward_num)
    
    # Get ward from database
    ward = Ward.query.filter_by(ward_number=ward_num).first_or_404()
    
    # Get all patients in this ward
    patients = Patient.query.filter_by(
        current_ward=ward_num, 
        is_active=True
    ).order_by(Patient.name).all()
    
    # Format patient data for template
    patient_data = {
        p.hospital_id: {
            "id": p.hospital_id,
            "name": p.name
        } for p in patients
    }
    
    # Log this access
    log_access('view_ward', f'Ward {ward_num}')
    
    return render_template('ward.html',
                         ward_num=ward_num,
                         ward_data={"patients": patient_data},
                         ward_name=ward.display_name,
                         pdf_filename="Database record", # Replace PDF filename reference
                         pdf_creation_time=ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward.last_updated else "Unknown")

@app.route('/search_ward/<ward_num>')
@login_required
def search_ward(ward_num):
    """Search endpoint for patients within a specific ward using database only"""
    ward_num = unquote(ward_num)
    search_query = request.args.get('q', '').strip().lower()
    
    # Base query for active patients in this ward
    query = Patient.query.filter_by(
        current_ward=ward_num, 
        is_active=True
    )
    
    # Apply search filter if query provided
    if search_query:
        query = query.filter(
            db.or_(
                Patient.hospital_id.ilike(f'%{search_query}%'),
                Patient.name.ilike(f'%{search_query}%')
            )
        )
    
    # Format results
    results = [
        {"id": patient.hospital_id, "name": patient.name}
        for patient in query.order_by(Patient.name).all()
    ]
    
    return jsonify(results)

@app.route('/search_wards')
@login_required
def search_wards():
    """Search for wards using database records only"""
    query = request.args.get('q', '').lower().strip()
    results = []
    
    # Base query for all active patients grouped by ward
    ward_counts = db.session.query(
        Patient.current_ward, 
        db.func.count(Patient.id)
    ).filter(
        Patient.is_active == True
    ).group_by(
        Patient.current_ward
    ).all()
    
    # Convert to dict for easy lookup
    count_map = dict(ward_counts)
    
    # Get all wards, filter by query if provided
    wards = Ward.query
    if query:
        wards = wards.filter(Ward.display_name.ilike(f'%{query}%'))
    
    # Format results
    for ward in wards.all():
        results.append({
            'ward_num': ward.ward_number,
            'display_name': ward.display_name,
            'patient_count': count_map.get(ward.ward_number, 0)
        })
    
    # Sort results: numeric wards first, then alphabetically
    results.sort(key=lambda x: (
        not x['ward_num'].isdigit(),
        int(x['ward_num']) if x['ward_num'].isdigit() else float('inf'),
        x['ward_num']
    ))
    
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
        print(f"Error recording recent view: {str(e)}")

    # Get all notes from database - already imported during init
    notes = Note.query.filter_by(patient_id=patient.id)\
        .order_by(Note.timestamp.desc()).all()
    
    # Get care notes added during downtime - MODIFY THIS SECTION
    care_notes = CareNote.query.filter_by(
        patient_id=patient_id  # Use patient_id directly since that's how we store it
    ).order_by(CareNote.timestamp.desc()).all()

    # Format notes for template
    formatted_notes = []
    
    # Add care notes with proper formatting
    for care_note in care_notes:
        care_dict = care_note.to_dict()
        # Use the imported staff_name if present; otherwise fallback to the related user's username
        if care_note.staff_name and care_note.staff_name.strip():
            care_dict['staff'] = care_note.staff_name
        else:
            user = User.query.get(care_note.user_id)
            care_dict['staff'] = user.username if user else 'Unknown'
        care_dict['date'] = care_dict['timestamp']  # Use timestamp as date
        if not care_note.is_pdf_note:
            care_dict['is_new'] = True
        formatted_notes.append(care_dict)

    # Sort all notes by timestamp
    formatted_notes.sort(
        key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S'), 
        reverse=True
    )

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
    """Return a standardized message - PDF viewing is deprecated"""
    log_access('view_pdf', patient_id)
    return """
    <div style="padding: 20px; font-family: Arial, sans-serif; text-align: center;">
        <h2>PDF Viewer Not Available</h2>
        <p>Individual PDF viewing has been deprecated. All patient data is now available in the main view.</p>
        <p>Please use the patient view page to access patient information.</p>
        <p><a href="/patient/{0}" style="color: #3182ce;">Return to Patient View</a></p>
    </div>
    """.format(patient_id)

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
    """Get patient count for a ward using direct database query"""
    ward_num = unquote(ward_num)
    
    # Get count of active patients in this ward
    count = Patient.query.filter_by(
        current_ward=ward_num,
        is_active=True
    ).count()
    
    return jsonify({
        "ward": ward_num,
        "count": count
    })

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
    """Add a care note to a patient using database only"""
    if not get_notes_enabled():
        flash('Note-adding functionality is currently disabled by the administrator', 'note-error')
        return redirect(url_for('patient', patient_id=patient_id))
        
    try:
        note_text = request.form.get('note')
        if not note_text:
            return jsonify({'error': 'Note text is required'}), 400
        
        # Get patient from database
        patient = Patient.query.filter_by(hospital_id=patient_id, is_active=True).first_or_404()
        
        # Create new care note
        note = CareNote(
            patient_id=patient_id,
            user_id=current_user.id,
            note=note_text,
            ward_id=patient.current_ward,
            patient_name=patient.name,
            is_pdf_note=False  # Always false for manually added notes
        )
        
        db.session.add(note)
        safe_commit()
        
        # Record in audit log
        log_access('add_note', patient_id)
        
        # Add success message
        session['care_note_success'] = 'Note added successfully!'
        session['new_note_id'] = note.id
        
        return redirect(url_for('patient', patient_id=patient_id))
        
    except Exception as e:
        print(f"Error adding care note: {str(e)}")
        flash('Error adding note. Please try again.', 'note-error')
        return redirect(url_for('patient', patient_id=patient_id))

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
            # Added staff_name to ensure it is passed in the JSON response:
            'staff_name': note.staff_name
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
def admin_timeout_settings():  # Changed function name to avoid conflict
    """Handle admin timeout settings updates"""
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

# Add this new route to handle ward search queries
@app.route('/search/<ward_id>')
@login_required 
def search_ward_patients(ward_id):
    """Search endpoint for patients within a specific ward using database only"""
    query = request.args.get('q', '').strip().lower()
    
    # Use database query with optional search filter
    base_query = Patient.query.filter_by(
        current_ward=ward_id,
        is_active=True
    )
    
    if query:
        base_query = base_query.filter(
            db.or_(
                Patient.hospital_id.ilike(f'%{query}%'),
                Patient.name.ilike(f'%{query}%')
            )
        )
    
    # Get patients ordered by name
    patients = base_query.order_by(Patient.name).all()
    
    # Format results
    results = [{
        'id': patient.hospital_id,
        'name': patient.name or 'Unknown'
    } for patient in patients]
    
    return jsonify(results)

@app.route('/admin/users')
@login_required
def admin_users():
    """Admin page for user management - allows adding users and resetting passwords"""
    # Only admins can access this page
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get all users
    users = User.query.order_by(User.username).all()
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/add_user', methods=['POST'])
@login_required
def admin_add_user():
    """Handle adding a new user"""
    # Only admins can access this function
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    
    # Basic validation
    if not username or not password:
        flash('Username and password are required', 'danger')
        return redirect(url_for('admin_users'))
    
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash(f'User "{username}" already exists', 'warning')
        return redirect(url_for('admin_users'))
    
    # Create new user
    new_user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{username}" created successfully', 'success')
        
        # Log this action
        log_access('create_user', f'Created user: {username}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/reset_password', methods=['POST'])
@login_required
def admin_reset_password():
    """Handle resetting a user's password"""
    # Only admins can access this function
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')
    
    # Basic validation
    if not user_id or not new_password:
        flash('User ID and new password are required', 'danger')
        return redirect(url_for('admin_users'))
    
    # Find the user
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
    
    # Update password
    try:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash(f'Password reset successful for user "{user.username}"', 'success')
        
        # Log this action
        log_access('reset_password', f'Reset password for user: {user.username}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/note_templates')
@login_required
def get_note_templates():
    """Get all active note templates"""
    templates = NoteTemplate.query.filter_by(is_active=True).order_by(NoteTemplate.name).all()
    return jsonify([{
        'id': template.id,
        'name': template.name,
        'content': template.content,
        'category': template.template_category.name if template.template_category else template.category or 'General'
    } for template in templates])

@app.route('/admin/templates', methods=['GET', 'POST', 'DELETE'])
@login_required
def admin_templates():
    """Admin page for managing note templates"""
    # Only admins can access this page
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Handle adding or editing templates
        template_id = request.form.get('template_id')
        name = request.form.get('name')
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        
        if not name or not content or not category_id:
            flash('Template name, content, and category are required', 'danger')
        else:
            if template_id:  # Edit existing
                template = NoteTemplate.query.get(template_id)
                if template:
                    template.name = name
                    template.content = content
                    template.category_id = category_id
                    db.session.commit()
                    flash(f'Template "{name}" updated successfully', 'success')
            else:  # Add new
                template = NoteTemplate(
                    name=name,
                    content=content,
                    category_id=category_id,
                    is_active=True
                )
                db.session.add(template)
                db.session.commit()
                flash(f'Template "{name}" added successfully', 'success')
        
        return redirect(url_for('admin_templates'))
    
    # Handle DELETE request (AJAX)
    if request.method == 'DELETE':
        data = request.get_json()
        template_id = data.get('template_id')
        
        template = NoteTemplate.query.get(template_id)
        if template:
            template.is_active = False  # Soft delete
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Template not found'}), 404
    
    # GET request - show template management page
    # Modified to handle both templates with and without category_id
    templates_query = db.session.query(
        NoteTemplate.id, 
        NoteTemplate.name, 
        NoteTemplate.content,
        NoteTemplate.category,
        TemplateCategory.id.label('category_id'),
        TemplateCategory.name.label('category_name')
    ).outerjoin(  # Use outerjoin to include templates without category_id
        TemplateCategory,
        NoteTemplate.category_id == TemplateCategory.id
    ).filter(
        NoteTemplate.is_active == True
    )
    
    # Apply order by
    templates = templates_query.order_by(
        TemplateCategory.name.nulls_last(),  # Handle NULL values in sorting 
        NoteTemplate.name
    ).all()
    
    # Get all categories - Remove filter that excludes admin category
    categories = []
    for cat in TemplateCategory.query.order_by(TemplateCategory.name).all():
        templates_count = NoteTemplate.query.filter_by(category_id=cat.id, is_active=True).count()
        categories.append({
            'id': cat.id,
            'name': cat.name,
            'has_templates': templates_count > 0
        })
    
    return render_template('admin_templates.html', templates=templates, categories=categories)

@app.route('/admin/templates/<int:template_id>')
@login_required
def get_template(template_id):
    """API endpoint to get a single template for editing"""
    if current_user.role != 'admin':
        return jsonify({"error": "Access denied"}), 403
        
    template = NoteTemplate.query.get_or_404(template_id)
    return jsonify({
        'id': template.id,
        'name': template.name,
        'content': template.content,
        'category_id': template.category_id
    })

@app.route('/admin/template-categories', methods=['POST', 'DELETE'])
@login_required
def manage_template_categories():
    """API endpoint to manage template categories"""
    if current_user.role != 'admin':
        return jsonify({"error": "Access denied"}), 403
    
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({"success": False, "error": "Category name is required"}), 400
        
        # Check if category already exists
        existing = TemplateCategory.query.filter_by(name(name)).first()
        if existing:
            return jsonify({"success": False, "error": "Category already exists"}), 400
        
        # Create new category
        category = TemplateCategory(name=name)
        db.session.add(category)
        db.session.commit()
        return jsonify({"success": True, "id": category.id, "name": category.name})
    
    if request.method == 'DELETE':
        data = request.get_json()
        category_id = data.get('category_id')
        force_delete = data.get('force_delete', False)
        
        # Check if category exists
        category = TemplateCategory.query.get_or_404(category_id)
        
        # Check if any templates use this category
        templates_count = NoteTemplate.query.filter_by(category_id=category_id).count()
        
        # If templates exist and force_delete is not True, return an error
        if templates_count > 0 and not force_delete:
            return jsonify({
                "success": False,
                "error": f"Cannot delete category that has {templates_count} templates",
                "templates_count": templates_count
            }), 400
        
        # If force_delete is True, reassign templates to NULL category
        if templates_count > 0 and force_delete:
            # Set category_id to NULL for all templates in this category
            NoteTemplate.query.filter_by(category_id=category_id).update({NoteTemplate.category_id: None})
            db.session.commit()
        
        # Delete the category
        db.session.delete(category)
        db.session.commit()
        return jsonify({"success": True})

@app.route('/update_timeout_settings_v2', methods=['POST'])  # Changed route name
@login_required
def update_timeout_settings_v2():  # Changed function name
    # Only admins can access this function
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Get form values
        timeout_enabled = request.form.get('timeout_enabled') is not None
        timeout_minutes = request.form.get('timeout_minutes', '30')
        
        # Save settings
        Settings.set_setting('timeout_enabled', str(timeout_enabled).lower())
        Settings.set_setting('timeout_minutes', timeout_minutes)
        
        # Log this change
        log_access('update_timeout', f'Updated timeout settings by {current_user.username}')
        
        flash('Session timeout settings updated', 'success')
    except Exception as e:
        db.session.rollback()
        log_access('update_timeout_error', f'Error updating timeout settings by {current_user.username}: {str(e)}')
        flash(f'Error updating timeout settings: {str(e)}', 'danger')
    
    return redirect(url_for('admin_notes'))

@app.route('/load_more_notes/<patient_id>/<int:offset>')
@login_required
def load_more_notes(patient_id, offset):
    """API endpoint to load additional care notes for a patient, including staff_name field."""
    # Load the next 20 care notes for the given patient_id ordered by timestamp descending
    care_notes = CareNote.query.filter_by(patient_id=patient_id)\
                    .order_by(CareNote.timestamp.desc())\
                    .offset(offset)\
                    .limit(20)\
                    .all()
    notes_data = []
    for note in care_notes:
        # Prefer the staff_name from the note; if not present, try to get the username from the related user.
        staff = note.staff_name if note.staff_name else (User.query.get(note.user_id).username if note.user_id else 'Unknown')
        note_dict = {
            'date': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'staff_name': note.staff_name,  # Directly included to be used by client-side code
            'staff': staff,
            'note': note.note,
            'is_new': not note.is_pdf_note
        }
        notes_data.append(note_dict)
    return jsonify({'notes': notes_data})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        db.create_all(bind=['audit'])
        # Create default admin user if not exists
        if not User.query.filter_by(username('admin')).first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
        # Create test user if not exists
        if not User.query.filter_by(username('nurse1')).first():
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