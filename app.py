import os
import re
import io
import csv
import json
import threading
import tempfile
from functools import lru_cache
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

# Flask imports
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

# Create Flask application
app = Flask(__name__)

# Load config
from config import Config
app.config.from_object(Config)

# Initialize database first
from database import db, init_app
init_app(app)

# Now initialize models after db is set up
from models import User, Ward, Patient, AuditLog, RecentlyViewedPatient, CareNote, Settings

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.session_protection = "strong"

# Import managers after models are initialized
from ward_manager import WardManager
from pdf_processor import process_ward_pdf
from simple_drive import SimpleDriveClient
from db_manager import DatabaseManager

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Print debug info
print("PDF Split App starting...")
print(f"Running from directory: {os.path.abspath('.')}")
print(f"Temporary directory: {tempfile.gettempdir()}")

# Initialize managers
ward_manager = WardManager()
db_manager = DatabaseManager()
drive_client = SimpleDriveClient()

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    db.create_all(bind=['audit'])

# Application globals
EXCEL_EXPORT_AVAILABLE = False  # Flag for Excel export capability

# Configuration with environment fallbacks
PDF_DIRECTORY = os.environ.get('PDF_DIRECTORY', os.path.join(os.getcwd(), 'pdfs'))
print(f"Using PDF directory: {os.path.abspath(PDF_DIRECTORY)}")

# Initialize ward manager
ward_manager.pdf_directory = PDF_DIRECTORY  # Update PDF directory path

# Try to import xlsxwriter but don't fail if not available
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

# Initialize models
import models
models.init_db(db)
models.register_models()  # Add this line to register the model classes
from models import User, AuditLog, RecentlyViewedPatient, CareNote, Settings
import click
from flask.cli import with_appcontext

# Now import init_database after models are registered
from init_db import init_database

# Initialize the database before defining routes
init_database(app)

# Helper function for Google Drive client
def get_drive_client():
    """Get or initialize the Google Drive client."""
    global drive_client
    if (drive_client is None):
        drive_client = SimpleDriveClient()
        
        # Try to initialize, with a fallback option if Google Drive is unavailable
        initialized = drive_client.initialize()
        if (not initialized):
            print("Warning: Failed to initialize drive client")
            
            # Create a local patching mechanism for the 'get_static_doc' issue
            try:
                from googleapiclient import discovery
                
                # Monkey patch the build function to avoid the get_static_doc error
                original_build = discovery.build
                def patched_build(*args, **kwargs):
                    kwargs['static_discovery'] = False
                    return original_build(*args, **kwargs)
                discovery.build = patched_build
                
                # Try again with the patched version
                print("Trying again with static_discovery=False...")
                initialized = drive_client.initialize()
                if (initialized):
                    print("Successfully initialized drive client with patch")
            except Exception as e:
                print(f"Failed to apply patch: {str(e)}")
    
    return drive_client

# Add this after creating the Flask app but before the routes
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

def get_notes_enabled():
    return Settings.get_setting('notes_enabled', 'true') == 'true'

def get_timeout_enabled():
    """Get the timeout enabled setting with a fallback"""
    try:
        return Settings.get_setting('timeout_enabled', 'true').lower() == 'true'
    except Exception:
        # Default to not timing out on error
        return False

def get_timeout_minutes():
    """Get the timeout minutes with a fallback"""
    try:
        minutes = Settings.get_setting('timeout_minutes', '30')
        return int(minutes)
    except (ValueError, Exception):
        # Default to 30 minutes on error
        return 30

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def log_access(action, patient_id=None):
    """Fix log_access to handle cases where user might not be authenticated"""
    try:
        if (current_user.is_authenticated):
            log = AuditLog(
                user_id=current_user.id,
                username=current_user.username,
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
    except Exception as e:
        print(f"Error in log_access: {str(e)}")

# REMOVED the extract_patient_info function as it's now in pdf_processor.py

# REMOVED the process_ward_pdf function as it's now in pdf_processor.py

# REMOVE the function implementations but keep function references 
# to maintain backwards compatibility during the transition
def get_ward_metadata():
    """Get ward metadata from ward_manager"""
    return ward_manager.get_ward_metadata(get_drive_client())

def load_specific_ward(ward_num):
    """Load a specific ward's data using ward_manager"""
    return ward_manager.load_specific_ward(ward_num)

def load_ward_patients(ward_num):
    """Load patient data for a specific ward using ward_manager"""
    return ward_manager.load_ward_patients(ward_num)

def load_ward_data_background():
    """Load ward metadata in a background thread using ward_manager"""
    ward_manager.load_ward_data_background(get_drive_client())

def init_ward_data():
    """Initialize ward data loading using ward_manager"""
    ward_manager.init_ward_data(get_drive_client())

def get_patient_info_from_ward_data(patient_id, ward_id=None):
    """Get patient information using ward_manager"""
    return ward_manager.get_patient_info_from_ward_data(patient_id, ward_id)

@app.before_first_request
def before_first_request():
    """Initialize data before first request."""
    # Initialize the drive client
    get_drive_client()
    
    # Initialize ward data
    init_ward_data()

# Update the ward route to use ward_manager
# @app.route('/ward/<ward_num>')
# @login_required
# def ward(ward_num):
#     """Ward view route handler"""
#     # URL decode the ward_num to handle special characters
#     ward_num = unquote(ward_num)
#     
#     print(f"Accessing ward: {ward_num}")
#     print(f"Available wards: {list(ward_manager.wards_data.keys())}")
#     
#     # Normalize ward number/name
#     normalized_ward = ward_num
#     if ward_num.lower().startswith('ward '):
#         normalized_ward = ward_num[5:].trip()  # Remove 'ward ' prefix
#     
#     # Reload ward metadata if empty
#     if not ward_manager.wards_data:
#         print("Ward data is empty, reloading metadata...")
#         # Initialize drive manager again if needed
#         if not drive_client:
#             get_drive_client()
#             
#         metadata = ward_manager.get_ward_metadata(get_drive_client())
#         if metadata:
#             ward_manager.wards_data.clear()
#             ward_manager.wards_data.update(metadata)
#             print(f"Reloaded metadata with {len(ward_manager.wards_data)} wards")
#     
#     # If still not found, try reloading one last time
#     if normalized_ward not in ward_manager.wards_data:
#         print(f"Ward {normalized_ward} not found, forcing metadata reload...")
#         # Try one more time with fresh SimpleDriveClient
#         dc = get_drive_client()
#         dc.initialize()
#         metadata = ward_manager.get_ward_metadata(dc)
#         if metadata:
#             ward_manager.wards_data.clear()
#             ward_manager.wards_data.update(metadata)
#             print(f"Reloaded metadata with {len(ward_manager.wards_data)} wards")
#     
#     # Try loading the ward data
#     try:
#         if normalized_ward in ward_manager.wards_data:
#             success = load_specific_ward(normalized_ward)
#             print(f"Load ward data result: {success}")
#             
#             # Debug output
#             if normalized_ward in ward_manager.wards_data:
#                 patients = ward_manager.wards_data[normalized_ward].get("patients", {})
#                 patient_count = len(patients)
#                 print(f"Ward {normalized_ward} has {patient_count} patients")
#                 if patient_count > 0:
#                     sample_ids = list(patients.keys())[:3]
#                     print(f"Sample patient IDs: {sample_ids}")
#         else:
#             print(f"Ward {normalized_ward} not found in available wards")
#     except Exception as e:
#         print(f"Error loading ward data: {str(e)}")
#         import traceback
#         traceback.print_exc()
#     
#     # Add audit log entry
#     log_access('view_ward', f'Ward {normalized_ward}')
#     
#     # Check if ward exists after all loading attempts
#     if normalized_ward not in ward_manager.wards_data:
#         print(f"Ward not found in wards_data: {normalized_ward}")
#         print(f"Available wards: {list(ward_manager.wards_data.keys())}")
#         flash("Ward not found", "error")
#         return redirect(url_for('index'))
#     
#     # Get ward info
#     ward_info = ward_manager.wards_data[normalized_ward]
#     
#     # Get PDF creation time (file modification time)
#     pdf_creation_time = "Unknown"
#     try:
#         if "file_id" in ward_info:
#             file_id = ward_info["file_id"]
#             local_path = get_drive_client().get_local_path(file_id, ward_info["filename"])
#             if local_path and os.path.exists(local_path):
#                 pdf_mtime = os.path.getmtime(local_path)
#                 pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
#         elif os.path.exists(ward_info["filename"]):
#             pdf_mtime = os.path.getmtime(ward_info["filename"])
#             pdf_creation_time = datetime.fromtimestamp(pdf_mtime).strftime("%Y-%m-%d %H:%M:%S")
#     except Exception as e:
#         print(f"Error getting file info: {str(e)}")
#     
#     # Render the ward template
#     return render_template('ward.html', 
#                          ward_num=normalized_ward,
#                          ward_data={"patients": ward_info.get("patients", {})},
#                          pdf_filename=ward_info["filename"],
#                          pdf_creation_time=pdf_creation_time,
#                          display_name=ward_info.get("display_name", normalized_ward))

# Update the search_ward route to use ward_manager
# @app.route('/search_ward/<ward_num>')
# @login_required
# def search_ward(ward_num):
#     ward_num = unquote(ward_num)
#     if ward_num not in ward_manager.wards_data:
#         return jsonify([])
#     search_query = request.args.get('q', '').strip().lower()
#     ward_patients = ward_manager.wards_data[ward_num].get("patients", {})
#     # If no search query, return all patients
#     if not search_query:
#         results = [{"id": pid, "name": data["name"]} 
#                   for pid, data in ward_patients.items()]
#     else:
#         # Search in both ID and name
#         results = [{"id": pid, "name": data["name"]} 
#                   for pid, data in ward_patients.items() 
#                   if search_query in pid.lower() or 
#                      search_query in data["name"].lower()]
#     return jsonify(results)

# Update the search_wards route to use ward_manager
# @app.route('/search_wards')
# @login_required
# def search_wards():
#     query = request.args.get('q', '').lower().trip()
#     results = []
#     # Handle "ward X" format by removing "ward" and trimming
#     if query.startswith('ward'):
#         query = query[4:].trip()
#     for ward_num, ward_info in ward_manager.wards_data.items():
#         # For numeric searches, be more precise
#         try:
#             search_num = query.trip()
#             ward_number = ward_num.trip()
#             if search_num and ward_number.isdigit():
#                 # Only match if it's the exact number or starts with the search number
#                 if ward_number == search_num or ward_number.startswith(search_num):
#                     patient_count = len(ward_info.get('patients', {}))
#                     results.append({
#                         'ward_num': ward_num,
#                         'filename': ward_info['filename'],
#                         'patient_count': patient_count
#                     })
#                 continue
#         except ValueError:
#             pass
#         # For non-numeric searches, use simple contains
#         if (query in ward_num.lower() or 
#             query in ward_info['filename'].lower()):
#             patient_count = len(ward_info.get('patients', {}))
#             results.append({
#                 'ward_num': ward_num,
#                 'filename': ward_info['filename'],
#                 'patient_count': patient_count
#             })
#     return jsonify(results)

# Update the patient route to use ward_manager
# @app.route('/patient/<patient_id>')
# @login_required
# def patient_view(patient_id):  # Changed the function name
#     """Patient view route handler using the database"""
#     try:
#         with db_manager.session_scope() as session:
#             # Get the patient from database
#             patient = session.query(Patient).filter_by(id=patient_id).first()
#             if not patient:
#                 flash(f"Patient {patient_id} not found", "error")
#                 return redirect(url_for('index'))
                
#             # Log this access
#             log_access('view_patient', patient_id)
            
#             # Add recently viewed record - but limit to prevent database bloat
#             try:
#                 # Check if patient was recently viewed to avoid duplicate entries
#                 recent_view = RecentlyViewedPatient.query.filter_by(
#                     user_id=current_user.id, 
#                     patient_id=patient_id
#                 ).first()
                
#                 if not recent_view:
#                     recent = RecentlyViewedPatient(
#                         user_id=current_user.id,
#                         patient_id=patient_id,
#                         ward_num=patient.ward_id,
#                         patient_name=patient.name
#                     )
#                     db.session.add(recent)
#                     # Limit to 10 recent patients per user
#                     older_views = RecentlyViewedPatient.query.filter_by(user_id=current_user.id)\
#                         .order_by(RecentlyViewedPatient.viewed_at.desc())\
#                         .offset(10).all()
#                     for old in older_views:
#                         db.session.delete(old)
#                     db.session.commit()
#                 else:
#                     # Update timestamp for existing view
#                     recent_view.viewed_at = datetime.utcnow()
#                     db.session.commit()
#             except Exception as e:
#                 # Log but don't fail the request if recording view history fails
#                 print(f"Error recording patient view: {str(e)}")
#                 db.session.rollback()
                
#             # Get the ward
#             ward = session.query(Ward).filter_by(id=patient.ward_id).first()
            
#             # Parse additional info JSON
#             patient_info_dict = {}
#             try:
#                 if patient.additional_info:
#                     patient_info_dict = json.loads(patient.additional_info)
#             except:
#                 patient_info_dict = {}
                
#             # Ensure patient info has all required fields
#             if "Patient ID" not in patient_info_dict:
#                 patient_info_dict["Patient ID"] = patient_id
#             if "Name" not in patient_info_dict:
#                 patient_info_dict["Name"] = patient.name
#             if "Ward" not in patient_info_dict:
#                 patient_info_dict["Ward"] = patient.ward_id
                
#             # Get care notes (pdf notes from database)
#             db_pdf_notes = session.query(CareNote).filter_by(
#                 patient_id=patient_id, is_pdf_note=True
#             ).order_by(CareNote.timestamp.desc()).all()
            
#             pdf_notes = []
#             for note in db_pdf_notes:
#                 pdf_notes.append({
#                     "date": note.timestamp.strftime("%Y-%m-%d %H:%M"),
#                     "staff": note.staff,
#                     "note": note.note,
#                     "is_pdf_note": True
#                 })
                
#             # Get user-added notes
#             db_notes = [n.to_dict() for n in CareNote.query.filter_by(
#                 patient_id=patient_id, is_pdf_note=False
#             ).order_by(CareNote.timestamp.desc()).all()]
            
#             for note in db_notes:
#                 user = User.query.get(note['user_id'])
#                 note['staff'] = user.username if user else 'Unknown'
#                 note['is_new'] = True
                
#             # Combine and sort notes (newest first)
#             combined = pdf_notes + db_notes
#             combined.sort(key=lambda n: n.get('timestamp') or n.get('date', ''), reverse=True)
            
#             # Get PDF file info
#             pdf_filename = ward.filename if ward else f"ward_{patient.ward_id}_records.pdf"
#             pdf_creation_time = ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward and ward.last_updated else "Unknown"
            
#             if 'care_note_success' in session:
#                 flash(session.pop('care_note_success'), 'success')
                
#             return render_template('patient.html',
#                                patient_id=patient_id,
#                                patient_info_dict=patient_info_dict,
#                                vitals=patient.vitals or "",
#                                care_notes=combined,
#                                ward_num=patient.ward_id,
#                                pdf_filename=pdf_filename,
#                                pdf_creation_time=pdf_creation_time,
#                                notes_enabled=get_notes_enabled())
#     except Exception as e:
#         print(f"Error displaying patient {patient_id}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         flash(f"Error loading patient: {str(e)}", "error")
#         return redirect(url_for('index'))

# Update the profile route to use ward_manager
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile route handler"""
    if (request.method == 'POST'):
        # Remove any note-related flash messages that might have persisted
        session.pop('_flashes', None)
        default_ward = request.form.get('default_ward')
        user = User.query.get(current_user.id)
        user.default_ward = default_ward
        db.session.commit()
        flash('Default ward updated successfully', 'success')
        return redirect(url_for('profile'))
    
    # Get wards for the dropdown
    wards = []
    try:
        with db_manager.session_scope() as session:
            for ward in session.query(Ward).all():
                wards.append({
                    'id': ward.id,
                    'display_name': ward.display_name or f"Ward {ward.id}"
                })
        wards.sort(key=lambda x: x['display_name'].lower())
    except Exception as e:
        print(f"Error loading wards for profile: {str(e)}")
    
    current_ward = current_user.default_ward or ""
    return render_template('profile.html', wards=wards, current_ward=current_ward)

# Update the index route to use ward_manager
@app.route('/')
@login_required
def index():
    """Modified index route with explicit login check and debug info"""
    show_all = request.args.get('show_all', '0') == '1'
    try:
        with db_manager.session_scope() as session:
            # Get all wards from database
            wards = session.query(Ward).all()
            
            # Format wards data for template
            sorted_wards = []
            for ward in wards:
                patient_count = session.query(Patient).filter_by(ward_id=ward.id).count()
                sorted_wards.append({
                    'id': ward.id,
                    'display_name': ward.display_name or f"Ward {ward.id}",
                    'filename': ward.filename or f"ward_{ward.id}_records.pdf",
                    'patient_count': patient_count
                })
            
            # Sort wards by display name
            sorted_wards.sort(key=lambda x: x['display_name'].lower())
            
            return render_template('index.html', wards=sorted_wards, show_all=show_all)
    except Exception as e:
        print(f"Error loading wards: {str(e)}")
        flash("Error loading wards", "error")
        return render_template('index.html', wards=[], show_all=show_all)

# Fix the login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Enhanced login with debugging"""
    # If already logged in, go to index
    if (current_user.is_authenticated):
        return redirect(url_for('index'))
        
    if (request.method == 'POST'):
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt for username: {username}")
        
        user = User.query.filter_by(username=username).first()
        
        if (user):
            print(f"User found in database: {user.username}, ID: {user.id}")
            password_match = check_password_hash(user.password_hash, password)
            print(f"Password match: {password_match}")
            
            if (password_match):
                print(f"Login successful for {user.username}")
                login_user(user, remember=True)
                session.permanent = True
                session['last_active'] = datetime.utcnow().timestamp()
                
                # Add additional session data to help with debugging
                session['user_id'] = user.id
                session['login_time'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                
                log_access('login')
                
                next_page = request.args.get('next')
                if (next_page and not next_page.startswith('/')):
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

# Enhance the ward route with better debugging
@app.route('/ward/<ward_num>')
@login_required
def ward(ward_num):
    """Ward view route handler using the database"""
    # URL decode the ward_num to handle special characters
    ward_num = unquote(ward_num)
    
    print(f"Accessing ward: {ward_num}")
    
    # Add audit log entry
    log_access('view_ward', f'Ward {ward_num}')
    
    try:
        with db_manager.session_scope() as session:
            # Get the ward from database
            ward = session.query(Ward).filter_by(id=ward_num).first()
            if (not ward):
                flash(f"Ward {ward_num} not found", "error")
                return redirect(url_for('index'))
                
            # Get patients in this ward
            patients = session.query(Patient).filter_by(ward_id=ward_num).all()
            
            if (not patients):
                flash(f"No patients found in ward {ward_num}", "warning")
            
            # Format patient data for the template
            patients_data = {}
            for patient in patients:
                # Parse additional info JSON
                try:
                    additional_info = json.loads(patient.additional_info) if patient.additional_info else {}
                except json.JSONDecodeError:
                    additional_info = {}
                    
                patients_data[patient.id] = {
                    "name": patient.name,
                    "info": additional_info
                }
            
            ward_data = {"patients": patients_data}
            
            # Get PDF creation time
            pdf_creation_time = ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward.last_updated else "Unknown"
            
            return render_template('ward.html',
                                 ward_num=ward_num,
                                 ward_data=ward_data,
                                 pdf_filename=ward.filename or f"ward_{ward_num}_records.pdf",
                                 pdf_creation_time=pdf_creation_time,
                                 display_name=ward.display_name)
                                 
    except Exception as e:
        print(f"Error displaying ward {ward_num}: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error loading ward: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/search_ward/<ward_num>')
@login_required
def search_ward(ward_num):
    """Search patients in a ward using the database"""
    ward_num = unquote(ward_num)
    search_query = request.args.get('q', '').strip().lower()
    
    try:
        with db_manager.session_scope() as session:
            # Get patients in this ward
            base_query = session.query(Patient).filter_by(ward_id=ward_num)
            
            if (search_query):
                # Filter by search term
                search_term = f"%{search_query}%"
                patients = base_query.filter(
                    or_(
                        Patient.id.like(search_term),
                        Patient.name.like(search_term)
                    )
                ).all()
            else:
                # Return all patients in the ward
                patients = base_query.all()
                
            # Format results for JSON response
            results = []
            for patient in patients:
                results.append({
                    "id": patient.id,
                    "name": patient.name
                })
                
            return jsonify(results)
            
    except Exception as e:
        print(f"Search error in ward {ward_num}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/search_wards')
@login_required
def search_wards():
    query = request.args.get('q', '').lower().strip()
    results = []
    
    try:
        with db_manager.session_scope() as session:
            # Base query for wards
            ward_query = session.query(Ward)
            
            # Apply search filter if query provided
            if (query):
                # Handle "ward X" format by removing "ward" prefix
                search_term = query
                if (query.startswith('ward')):
                    search_term = query[4:].strip()
                
                # Search in ward ID and display name
                ward_query = ward_query.filter(
                    or_(
                        Ward.id.ilike(f"%{search_term}%"),
                        Ward.display_name.ilike(f"%{search_term}%"),
                        Ward.filename.ilike(f"%{search_term}%")
                    )
                )
            
            # Execute query and format results
            for ward in ward_query.all():
                patient_count = session.query(Patient).filter_by(ward_id=ward.id).count()
                results.append({
                    'id': ward.id,
                    'ward_num': ward.id,  # Keep for backward compatibility
                    'display_name': ward.display_name or f"Ward {ward.id}",
                    'filename': ward.filename or f"ward_{ward.id}_records.pdf",
                    'patient_count': patient_count
                })
                
        return jsonify(results)
    except Exception as e:
        print(f"Error searching wards: {str(e)}")
        return jsonify([])

@app.route('/patient/<patient_id>')
@login_required
def patient(patient_id):
    """Patient view route handler using the database"""
    try:
        with db_manager.session_scope() as session:
            # Get the patient from database
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if (not patient):
                flash(f"Patient {patient_id} not found", "error")
                return redirect(url_for('index'))
                
            # Log this access
            log_access('view_patient', patient_id)
            
            # Add recently viewed record - but limit to prevent database bloat
            try:
                # Check if patient was recently viewed to avoid duplicate entries
                recent_view = RecentlyViewedPatient.query.filter_by(
                    user_id=current_user.id, 
                    patient_id=patient_id
                ).first()
                
                if (not recent_view):
                    recent = RecentlyViewedPatient(
                        user_id=current_user.id,
                        patient_id=patient_id,
                        ward_num=patient.ward_id,
                        patient_name=patient.name
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
                
            # Get the ward
            ward = session.query(Ward).filter_by(id=patient.ward_id).first()
            
            # Parse additional info JSON
            patient_info_dict = {}
            try:
                if (patient.additional_info):
                    patient_info_dict = json.loads(patient.additional_info)
            except:
                patient_info_dict = {}
                
            # Ensure patient info has all required fields
            if ("Patient ID" not in patient_info_dict):
                patient_info_dict["Patient ID"] = patient_id
            if ("Name" not in patient_info_dict):
                patient_info_dict["Name"] = patient.name
            if ("Ward" not in patient_info_dict):
                patient_info_dict["Ward"] = patient.ward_id
                
            # Get care notes (pdf notes from database)
            db_pdf_notes = session.query(CareNote).filter_by(
                patient_id=patient_id, is_pdf_note=True
            ).order_by(CareNote.timestamp.desc()).all()
            
            pdf_notes = []
            for note in db_pdf_notes:
                pdf_notes.append({
                    "date": note.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "staff": note.staff,
                    "note": note.note,
                    "is_pdf_note": True
                })
                
            # Get user-added notes
            db_notes = [n.to_dict() for n in CareNote.query.filter_by(
                patient_id=patient_id, is_pdf_note=False
            ).order_by(CareNote.timestamp.desc()).all()]
            
            for note in db_notes:
                user = User.query.get(note['user_id'])
                note['staff'] = user.username if user else 'Unknown'
                note['is_new'] = True
                
            # Combine and sort notes (newest first)
            combined = pdf_notes + db_notes
            combined.sort(key=lambda n: n.get('timestamp') or n.get('date', ''), reverse=True)
            
            # Get PDF file info
            pdf_filename = ward.filename if ward else f"ward_{patient.ward_id}_records.pdf"
            pdf_creation_time = ward.last_updated.strftime("%Y-%m-%d %H:%M:%S") if ward and ward.last_updated else "Unknown"
            
            if ('care_note_success' in session):
                flash(session.pop('care_note_success'), 'success')
                
            return render_template('patient.html',
                               patient_id=patient_id,
                               patient_info_dict=patient_info_dict,
                               vitals=patient.vitals or "",
                               care_notes=combined,
                               ward_num=patient.ward_id,
                               pdf_filename=pdf_filename,
                               pdf_creation_time=pdf_creation_time,
                               notes_enabled=get_notes_enabled())
    except Exception as e:
        print(f"Error displaying patient {patient_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error loading patient: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/pdf/<patient_id>')
@login_required
def serve_patient_pdf(patient_id):
    try:
        with db_manager.session_scope() as session:
            # Find the patient in the database
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if (not patient):
                return "Patient not found", 404

            # Log this access
            log_access('view_pdf', patient_id)
            
            # Get the ward information
            ward = session.query(Ward).filter_by(id=patient.ward_id).first()
            ward_filename = ward.filename if ward else f"ward_{patient.ward_id}_records.pdf"
            
            # Return a response with instructions to create a proper PDF viewer
            return """
            <div style="padding: 20px; font-family: Arial, sans-serif; text-align: center;">
                <h2>PDF Viewer Not Available</h2>
                <p>Individual PDF extraction for patient records is not implemented in this version.</p>
                <p>Patient data is displayed in the main patient view.</p>
            </div>
            """
    except Exception as e:
        print(f"Error serving PDF for patient {patient_id}: {str(e)}")
        return "Error accessing patient PDF", 500

@app.route('/recent_patients')
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
        if (recent.patient_id not in seen_patients):
            unique_recents.append(recent)
            seen_patients.add(recent.patient_id)
            # Stop once we have 10 unique patients
            if (len(unique_recents) >= 10):
                break
    return jsonify([r.to_dict() for r in unique_recents])

@app.route('/admin/toggle_notes', methods=['POST'])
@login_required
def toggle_notes():
    if (current_user.role != 'admin'):
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
    if (not get_notes_enabled()):
        flash('Note-adding functionality is currently disabled by the administrator', 'note-error')
        return redirect(url_for('patient', patient_id=patient_id))
    try:
        note_text = request.form.get('note')
        if (not note_text):
            return jsonify({'error': 'Note text is required'}), 400
            
        # Find which ward this patient belongs to and get patient name
        ward_id = None
        patient_name = "Unknown"
        ward_data = ward_manager.wards_data
        for ward_num, ward_info in ward_data.items():
            if (ward_info.get("patients") and patient_id in ward_info.get("patients", {})):
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
        # Record in audit log
        log_access('add_note', patient_id)
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
    """Show notes added by the current user during their shift"""
    show_all = request.args.get('show_all', '0') == '1'
    
    try:
        with db_manager.session_scope() as session:
            # Get ward names mapping
            wards = {ward.id: ward.display_name for ward in session.query(Ward).all()}
            
            # Check if is_pdf_note column exists
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('care_note')]
            has_pdf_note_column = 'is_pdf_note' in columns
            
            # Query for care notes
            if (has_pdf_note_column):
                # Use is_pdf_note field if it exists
                query = session.query(CareNote).filter_by(
                    user_id=current_user.id,
                    is_pdf_note=False
                )
            else:
                # Fall back to just user_id if column doesn't exist yet
                query = session.query(CareNote).filter_by(
                    user_id=current_user.id
                )
                
            if (not show_all):
                # Only show notes from the last 24 hours
                cutoff = datetime.now() - timedelta(days=1)
                query = query.filter(CareNote.timestamp >= cutoff)
                
            notes = query.order_by(CareNote.timestamp.desc()).all()
            
            return render_template(
                'shift_notes.html',
                notes=notes,
                show_all=show_all,
                ward_names=wards
            )
    except Exception as e:
        print(f"Error loading shift notes: {str(e)}")
        flash("Error loading shift notes", "error")
        return redirect(url_for('index'))

@app.route('/admin/notes')
@login_required
def admin_notes():
    # Only admins can access this page
    if (current_user.role != 'admin'):
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get filter parameters with explicit empty defaults
    ward_id = request.args.get('ward', '')
    username = request.args.get('username', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    
    # Debug output to console
    print(f"Received filter params - ward_id: '{ward_id}', username: '{username}'")
    
    # Build query with filters
    query = CareNote.query
    
    # Track whether any filters are applied
    filters_applied = False
    
    # Apply user filter by username
    if (username):
        # Get all users matching the username pattern
        matching_users = User.query.filter(User.username.like(f'%{username}%')).all()
        filtered_user_ids = [u.id for u in matching_users]
        if (filtered_user_ids):
            query = query.filter(CareNote.user_id.in_(filtered_user_ids))
        else:
            # No matching users, return empty result
            query = query.filter(CareNote.id < 0)
        filters_applied = True
    
    # Apply date filters
    if (date_from):
        filters_applied = True
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(CareNote.timestamp >= date_from_obj)
        except ValueError:
            pass
    if (date_to):
        filters_applied = True
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(CareNote.timestamp <= date_to_obj)
        except ValueError:
            pass
    
    # Apply ward filter - ensure it's a non-empty string
    if (ward_id and ward_id.strip()):
        filters_applied = True
        query = query.filter(CareNote.ward_id == ward_id)
        print(f"Applied ward filter: {ward_id}")
    
    # Count total matching notes before pagination
    total_notes = query.count()
    
    # Paginate the query
    paginated_notes = query.order_by(CareNote.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get all users from the notes for batch processing
    user_ids = list(set(note.user_id for note in CareNote.query.with_entities(CareNote.user_id).distinct()))
    if (user_ids):
        users = User.query.filter(User.id.in_(user_ids)).all()
        users_map = {user.id: user.username for user in users}
    else:
        users_map = {}
    
    # Get ward display names for dropdown
    available_wards = {}
    try:
        # Use the database instead of ward_manager.wards_data
        with db_manager.session_scope() as session:
            wards = session.query(Ward).all()
            for ward in wards:
                available_wards[ward.id] = {
                    "display_name": ward.display_name or f"Ward {ward.id}",
                    "filename": ward.filename
                }
    except Exception as e:
        print(f"Error loading wards for dropdown: {str(e)}")
    
    # Sort wards alphabetically by display name for better UX
    available_wards = dict(sorted(
        available_wards.items(),
        key=lambda item: item[1]["display_name"].lower() if isinstance(item[1], dict) and "display_name" in item[1] else item[0].lower()
    ))
    
    # Get all available usernames for the filter dropdown from notes
    available_usernames = sorted([users_map.get(uid) for uid in user_ids if uid in users_map])
    
    # Preserve the exact ward_id from request parameters
    selected_ward = request.args.get('ward', '')
    print(f"Filter selected_ward: '{selected_ward}'")
    
    filters = {
        'ward': selected_ward,
        'username': username,
        'date_from': date_from,
        'date_to': date_to,
        'applied': filters_applied
    }
    
    # Debug the filters being passed to template
    print(f"Filters passed to template: {filters}")
    
    # Process notes for display
    notes = []
    for note in paginated_notes.items:
        # Get ward name efficiently using our preloaded display names
        ward_info = available_wards.get(note.ward_id)
        if (isinstance(ward_info, dict) and 'display_name' in ward_info):
            ward_name = ward_info['display_name']
        else:
            ward_name = note.ward_id or "Unknown"
        # Use stored patient name and get username from preloaded map
        patient_name = note.patient_name or "Unknown"
        username_display = users_map.get(note.user_id, "Unknown")
        notes.append({
            'timestamp': note.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'patient_id': note.patient_id,
            'patient_name': patient_name,
            'note': note.note,
            'ward': ward_name,
            'username': username_display
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
                          next_page=paginated_notes.next_num or page)

@app.route('/admin/notes/export/<format>')
@login_required
def export_notes(format):
    # Only admins can access this feature
    if (current_user.role != 'admin'):
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
    if (username):
        matching_users = User.query.filter(User.username.like(f'%{username}%')).all()
        filtered_user_ids = [u.id for u in matching_users]
        if (filtered_user_ids):
            query = query.filter(CareNote.user_id.in_(filtered_user_ids))
        else:
            query = query.filter(CareNote.id < 0)
    
    # Apply date filters
    if (date_from):
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(CareNote.timestamp >= date_from_obj)
        except ValueError:
            pass
    if (date_to):
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(CareNote.timestamp <= date_to_obj)
        except ValueError:
            pass
    
    # Apply ward filter - ensure it's a non-empty string
    if (ward_id and ward_id.strip()):
        query = query.filter(CareNote.ward_id == ward_id)
    
    # Get the filtered notes
    notes = query.order_by(CareNote.timestamp.desc()).all()
    
    # Pre-load all users for efficiency
    user_ids = list(set(note.user_id for note in notes))
    users = User.query.filter(User.id.in_(user_ids)).all()
    users_map = {user.id: user.username for user in users}
    
    # Pre-load ward display names
    ward_display_names = {ward_id: info.get("display_name", ward_id) for ward_id, info in ward_manager.wards_data.items()}
    
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
    
    if (format == 'excel'):
        if (not EXCEL_EXPORT_AVAILABLE):
            error_msg = "Excel export is not available. Please ensure xlsxwriter package is installed."
            print(error_msg)  # Log to server console
            flash(error_msg, 'error')
            return redirect(url_for('admin_notes'))
        return export_excel(export_data)
    elif (format == 'pdf'):
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
                table_data.append([
                    item['timestamp'],
                    item['ward'],
                    item['patient_name'],
                    item['username'],
                    item['note']
                ])
        table = Table(table_data, colWidths=[80, 60, 80, 60, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
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
    # Store referrer for better navigation
    if (request.endpoint and 'static' not in request.endpoint and request.method == 'GET'):
        # Don't store referrers for logout, login or these specific endpoints
        excluded_endpoints = ['logout', 'login', 'serve_static']
        if (request.endpoint not in excluded_endpoints):
            session['last_page'] = request.url

# Fix the check_session_timeout function
@app.before_request
def check_session_timeout():
    """Improved session timeout check with better debugging"""
    if (current_user.is_authenticated and request.endpoint not in ['static', 'logout']):
        if (get_timeout_enabled()):
            try:
                last_active = session.get('last_active')
                if (last_active is None):
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
                
                if (time_diff > timedelta(minutes=timeout_minutes)):
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
                
@app.route('/admin/timeout_settings', methods=['POST'])
@login_required
def update_timeout_settings():
    if (current_user.role != 'admin'):
        flash('Access denied')
        return redirect(url_for('index'))
    
    enabled = request.form.get('timeout_enabled') == '1'
    minutes_str = request.form.get('timeout_minutes', '')
    
    # Validate input
    if (not minutes_str.isdigit()):
        flash('Timeout must be a positive number', 'error')
        return redirect(url_for('admin_notes'))
    minutes = int(minutes_str)
    if (minutes < 1 or minutes > 1440):  # 1440 minutes = 24 hours
        flash('Timeout must be between 1 and 1440 minutes', 'error')
        return redirect(url_for('admin_notes'))
    
    Settings.set_setting('timeout_enabled', str(enabled).lower())
    Settings.set_setting('timeout_minutes', str(minutes))
    flash('Session timeout settings updated successfully', 'success')
    return redirect(url_for('admin_notes'))

@app.route('/audit-log')
@login_required
def view_audit_log():
    """View audit log entries"""
    try:
        with db_manager.session_scope() as session:
            # Get all audit log entries, ordered by timestamp descending
            logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
            return render_template('audit_log.html', logs=logs)
    except Exception as e:
        print(f"Error viewing audit log: {str(e)}")
        flash('Error loading audit log', 'error')
        return redirect(url_for('index'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database (creates tables if missing)."""
    db.create_all()
    click.echo('Database initialized.')

app.cli.add_command(init_db_command)

if __name__ == '__main__':
    try:
        # Initialize the drive client with error handling
        if (not drive_client.initialize()):
            print("Warning: Drive client initialization failed, some features may be limited")
        else:
            print("Drive client initialized successfully")
            
        with app.app_context():
            db.create_all()
            db.create_all(bind=['audit'])
            # Create default admin user if not exists
            if (not User.query.filter_by(username='admin').first()):
                admin = User(
                    username='admin',
                    password_hash=generate_password_hash('admin123'),
                    role='admin'
                )
                db.session.add(admin)
            # Create test user if not exists
            if (not User.query.filter_by(username='nurse1').first()):
                test_user = User(
                    username='nurse1',
                    password_hash=generate_password_hash('nurse123'),
                    role='user'
                )
                db.session.add(test_user)
            db.session.commit()
            
        app.run(debug=True)
    except Exception as e:
        print(f"Error during startup: {str(e)}")
        import traceback
        traceback.print_exc()