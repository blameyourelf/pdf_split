from app import app, db, CareNote
from models import Ward, Patient, Note, User, Settings
from werkzeug.security import generate_password_hash
import logging
import os
import re
import shutil
from datetime import datetime
from PyPDF2 import PdfReader
from sqlalchemy import inspect, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_databases():
    """Create backups of existing databases"""
    logger.info("Creating database backups...")
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_created = False
    
    for db_file in ['users.db', 'audit.db', 'pdf_parsed.db']:
        db_path = os.path.join('instance', db_file)
        if os.path.exists(db_path):
            backup_path = os.path.join(backup_dir, f'{db_file}_{timestamp}')
            shutil.copy2(db_path, backup_path)
            logger.info(f"Backed up {db_file} to {backup_path}")
            backup_created = True
    
    if not backup_created:
        logger.info("No existing databases found to backup")
    
    return True

def parse_pdf_content(pdf_path, patient_id=None):
    """Extract patient info and notes from PDF file"""
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
                
            # Extract patient ID
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
                    care_notes_text = text
                    if "Continuous Care Notes" in text:
                        care_notes_section = text.split("Continuous Care Notes", 1)
                        if len(care_notes_section) > 1:
                            care_notes_text = care_notes_section[1].strip()
                    
                    # Extract individual notes using regex pattern
                    care_notes_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+([^,]+(?:, [A-Z]+)?)\s+(.+?)(?=(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2})|$)"
                    matches = list(re.finditer(care_notes_pattern, care_notes_text, re.DOTALL))
                    
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
            
        # Don't forget to add the last patient
        if current_patient_id and current_patient:
            if not patient_id or current_patient_id == patient_id:
                patient_data[current_patient_id] = current_patient
                
        return patient_data
        
    except Exception as e:
        logger.error(f"PDF parsing error: {str(e)}")
        return {}

def apply_indexes():
    """Apply all indexes to the databases"""
    logger.info("Applying database indexes...")
    
    with app.app_context():
        # Group 1: Main database indexes
        main_db_indexes = [
            # User table indexes
            ('CREATE INDEX IF NOT EXISTS idx_user_username ON user (username)'),
            ('CREATE INDEX IF NOT EXISTS idx_user_role ON user (role)'),
            
            # Care Note indexes
            ('CREATE INDEX IF NOT EXISTS idx_carenote_patient_id ON care_note (patient_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_timestamp ON care_note (timestamp DESC)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_user_id ON care_note (user_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_ward_id ON care_note (ward_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_is_pdf_note ON care_note (is_pdf_note)'),
            
            # Recently viewed patients
            ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_user_id ON recently_viewed_patient (user_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_timestamp ON recently_viewed_patient (viewed_at DESC)'),
            
            # Settings and templates
            ('CREATE INDEX IF NOT EXISTS idx_settings_key ON settings (key)'),
            ('CREATE INDEX IF NOT EXISTS idx_note_template_category ON note_template (category_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_note_template_active ON note_template (is_active)')
        ]
        
        # Apply main DB indexes
        for index_sql in main_db_indexes:
            try:
                logger.info(f"Applying to main DB: {index_sql}")
                db.session.execute(text(index_sql))
                db.session.commit()
            except Exception as e:
                logger.error(f"Error applying index: {str(e)}")
                db.session.rollback()
        
        # Group 2: pdf_parsed database indexes
        try:
            pdf_parsed_engine = db.get_engine(app, 'pdf_parsed')
            pdf_parsed_indexes = [
                ('CREATE INDEX IF NOT EXISTS idx_patient_hospital_id ON patient (hospital_id)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_current_ward ON patient (current_ward)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_is_active ON patient (is_active)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_name ON patient (name)'),
                ('CREATE INDEX IF NOT EXISTS idx_ward_ward_number ON ward (ward_number)')
            ]
            
            for index_sql in pdf_parsed_indexes:
                try:
                    logger.info(f"Applying to pdf_parsed DB: {index_sql}")
                    pdf_parsed_engine.execute(text(index_sql))
                except Exception as e:
                    logger.error(f"Error applying index to pdf_parsed DB: {str(e)}")
        except Exception as e:
            logger.error(f"Error accessing pdf_parsed database: {str(e)}")
        
        # Group 3: audit database indexes
        try:
            audit_engine = db.get_engine(app, 'audit')
            audit_indexes = [
                ('CREATE INDEX IF NOT EXISTS idx_auditlog_timestamp ON audit_log (timestamp DESC)'),
                ('CREATE INDEX IF NOT EXISTS idx_auditlog_user_id ON audit_log (user_id)')
            ]
            
            for index_sql in audit_indexes:
                try:
                    logger.info(f"Applying to audit DB: {index_sql}")
                    audit_engine.execute(text(index_sql))
                except Exception as e:
                    logger.error(f"Error applying index to audit DB: {str(e)}")
        except Exception as e:
            logger.error(f"Error accessing audit database: {str(e)}")

def reset_and_initialize_system():
    """Reset databases and initialize with PDF data"""
    with app.app_context():
        try:
            # Step 1: Backup existing databases
            backup_databases()
            
            # Step 2: Drop all tables and create fresh schema
            logger.info("Dropping and recreating all tables...")
            db.drop_all()
            db.drop_all(bind=['audit', 'pdf_parsed'])
            db.create_all()
            db.create_all(bind=['audit', 'pdf_parsed'])
            
            # Step 3: Create admin user
            logger.info("Creating admin user...")
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
            # Step 4: Create nurse user
            nurse = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(nurse)
            
            # Step 5: Initialize settings
            logger.info("Initializing system settings...")
            Settings.set_setting('notes_enabled', 'true')
            Settings.set_setting('timeout_enabled', 'true')
            Settings.set_setting('timeout_minutes', '60')
            
            # Commit initial setup
            db.session.commit()
            
            # Step 6: Process PDF files and import data
            logger.info("Processing ward PDF files...")
            pdf_files = [f for f in os.listdir('.') if f.startswith('ward_') and f.endswith('_records.pdf')]
            logger.info(f"Found {len(pdf_files)} ward PDF files")
            
            total_patients = 0
            total_notes = 0
            
            for pdf_file in pdf_files:
                ward_num = pdf_file[5:-12]  # Remove 'ward_' and '_records.pdf'
                display_name = f"Ward {ward_num}" if ward_num.isdigit() else ward_num.replace('_', ' ')
                
                # Create or update ward record
                ward = Ward.query.filter_by(ward_number=ward_num).first()
                if not ward:
                    ward = Ward(
                        ward_number=ward_num,
                        display_name=display_name,
                        pdf_file=pdf_file,
                        last_updated=datetime.utcnow()
                    )
                    db.session.add(ward)
                else:
                    ward.pdf_file = pdf_file
                    ward.last_updated = datetime.utcnow()
                
                db.session.commit()
                
                # Import PDF data
                logger.info(f"Processing {pdf_file}...")
                patient_data = parse_pdf_content(pdf_file)
                ward_patients = len(patient_data)
                total_patients += ward_patients
                logger.info(f"Found {ward_patients} patients in {pdf_file}")
                
                # Process each patient
                for patient_id, info in patient_data.items():
                    # Create or update patient
                    patient = Patient.query.filter_by(hospital_id=patient_id).first()
                    if not patient:
                        patient = Patient(
                            hospital_id=patient_id,
                            name=info['name'],
                            dob=info['info'].get('DOB', ''),
                            current_ward=ward_num
                        )
                        db.session.add(patient)
                        logger.debug(f"Added patient: {patient_id} - {info['name']}")
                    
                    # Add care notes directly to CareNote table
                    notes_count = len(info.get('care_notes', []))
                    
                    for note_data in info['care_notes']:
                        timestamp = datetime.strptime(note_data['date'], '%Y-%m-%d %H:%M')
                        
                        # Create CareNote
                        carenote = CareNote(
                            patient_id=patient_id,
                            ward_id=ward_num,
                            timestamp=timestamp,
                            staff_name=note_data['staff'],
                            note=note_data['note'],
                            patient_name=info['name'],
                            is_pdf_note=True
                        )
                        db.session.add(carenote)
                        total_notes += 1
                    
                    # Commit after each patient to avoid large transactions
                    db.session.commit()
            
            logger.info(f"Reset and initialization complete. Added {total_patients} patients and {total_notes} care notes.")
            
            # Step 7: Apply database indexes
            logger.info("Applying database indexes...")
            apply_indexes()
            logger.info("Database indexes applied successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Reset and initialization failed: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    # Ask for confirmation before proceeding
    response = input("This will reset ALL databases and lose all data. Are you sure you want to proceed? (y/n): ")
    if response.lower() == 'y':
        reset_and_initialize_system()
    else:
        print("Reset and initialization cancelled.")