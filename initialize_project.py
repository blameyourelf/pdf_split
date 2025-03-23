from app import app, db
from models import (
    User, Settings, TemplateCategory, NoteTemplate, 
    Ward, CareNote, Patient, Note, AuditLog
)
from werkzeug.security import generate_password_hash
from datetime import datetime, UTC
from sqlalchemy import inspect, text
import os
import re
import shutil
import sys
import logging
from PyPDF2 import PdfReader
from config import Config

# Add migrations directory to path for importing apply_indexes
sys.path.append(os.path.join(os.path.dirname(__file__), 'migrations'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_database():
    """Create backup of existing database files"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for db_file in ['users.db', 'audit.db', 'pdf_parsed.db']:
        db_path = os.path.join('instance', db_file)
        if os.path.exists(db_path):
            backup_path = os.path.join(backup_dir, f'{db_file}_{timestamp}')
            shutil.copy2(db_path, backup_path)
            logger.info(f"Backed up {db_file} to {backup_path}")

def parse_pdf_content(pdf_path, patient_id=None):
    """Extract patient info and notes from PDF file"""
    try:
        reader = PdfReader(pdf_path)
        all_text = ""
        
        for page in reader.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"
                
        # Extract patient information
        patient_info = {}
        
        # Look for NHS number and hospital ID
        nhs_match = re.search(r"NHS Number:\s*([0-9\s]+)", all_text)
        if nhs_match:
            patient_info['nhs_number'] = nhs_match.group(1).strip()
            
        hospital_id_match = re.search(r"Hospital ID:\s*([A-Z0-9]+)", all_text)
        if hospital_id_match:
            patient_info['hospital_id'] = hospital_id_match.group(1).strip()
            
        # Extract patient name
        name_match = re.search(r"Patient Name:\s*([^\n]+)", all_text)
        if name_match:
            patient_info['name'] = name_match.group(1).strip()
            
        # Extract DOB
        dob_match = re.search(r"DOB:\s*(\d{2}/\d{2}/\d{4})", all_text)
        if dob_match:
            patient_info['dob'] = dob_match.group(1).strip()
            
        # Extract gender
        gender_match = re.search(r"Gender:\s*([^\n]+)", all_text)
        if gender_match:
            patient_info['gender'] = gender_match.group(1).strip()
            
        # Extract consultant
        consultant_match = re.search(r"Consultant:\s*([^\n]+)", all_text)
        if consultant_match:
            patient_info['consultant'] = consultant_match.group(1).strip()
        
        # Extract clinical notes section
        notes = []
        notes_section = re.search(r"Clinical Notes:(.*?)(?:\n\s*[A-Z][A-Z\s]+:|\Z)", all_text, re.DOTALL)
        if notes_section:
            notes_text = notes_section.group(1).strip()
            
            # Split into individual notes
            note_entries = re.findall(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+[^\n]+(?:\n(?!\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}).+)*)", notes_text)
            
            for entry in note_entries:
                # Extract timestamp and content
                timestamp_match = re.match(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s+(.*)", entry, re.DOTALL)
                if timestamp_match:
                    timestamp_str, content = timestamp_match.groups()
                    try:
                        # Convert DD/MM/YYYY HH:MM to datetime
                        timestamp = datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M")
                        notes.append({
                            'timestamp': timestamp,
                            'content': content.strip(),
                            'patient_id': patient_id
                        })
                    except ValueError:
                        logger.warning(f"Invalid timestamp format: {timestamp_str}")
        
        return patient_info, notes
    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {str(e)}")
        return None, []

def extract_patient_data(pdf_path, ward_number):
    """Extract patient and notes data from a single PDF file and save directly to database"""
    try:
        # Get ward from database
        ward = Ward.query.filter_by(ward_number=ward_number).first()
        if not ward:
            logger.error(f"Ward {ward_number} not found in database.")
            return False
        
        # Extract patient data and notes from PDF
        patient_info, _ = parse_pdf_content(pdf_path)
        if not patient_info:
            logger.error(f"Failed to extract patient information from {pdf_path}")
            return False
        
        # Create or update patient record
        if 'hospital_id' not in patient_info:
            logger.error(f"No hospital ID found in {pdf_path}")
            return False
        
        # Set default values for missing fields
        patient_info.setdefault('name', 'Unknown')
        patient_info.setdefault('dob', None)
        patient_info.setdefault('gender', 'Unknown')
        patient_info.setdefault('consultant', 'Unknown')
        
        # Check if patient exists in the pdf_parsed database
        patient = Patient.query.filter_by(hospital_id=patient_info['hospital_id']).first()
        
        if not patient:
            # Create new patient
            patient = Patient(
                hospital_id=patient_info['hospital_id'],
                name=patient_info['name'],
                dob=datetime.strptime(patient_info['dob'], "%d/%m/%Y") if patient_info['dob'] else None,
                gender=patient_info['gender'],
                current_ward=ward_number,
                consultant=patient_info['consultant'],
                is_active=True
            )
            db.session.add(patient)
        else:
            # Update existing patient
            patient.name = patient_info['name']
            patient.dob = datetime.strptime(patient_info['dob'], "%d/%m/%Y") if patient_info['dob'] else patient.dob
            patient.gender = patient_info['gender']
            patient.current_ward = ward_number
            patient.consultant = patient_info['consultant']
            patient.is_active = True
        
        db.session.commit()
        
        # Now re-extract notes with the patient_id
        _, notes = parse_pdf_content(pdf_path, patient.id)
        
        # Add notes to CareNote table (main database)
        for note_data in notes:
            care_note = CareNote(
                patient_id=patient.id,
                ward_id=ward.id,
                timestamp=note_data['timestamp'],
                content=note_data['content'],
                is_pdf_note=True
            )
            db.session.add(care_note)
        
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error extracting patient data from {pdf_path}: {str(e)}")
        db.session.rollback()
        return False

def process_ward_pdfs():
    """Process all ward PDF files in the current directory"""
    pdf_files = [f for f in os.listdir('.') if f.startswith('ward_') and f.endswith('_records.pdf')]
    logger.info(f"Found {len(pdf_files)} ward PDF files")
    
    success_count = 0
    failure_count = 0
    
    for pdf_file in pdf_files:
        # Extract ward number from filename
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
        
        logger.info(f"Processing {pdf_file}...")
        if extract_patient_data(pdf_file, ward_num):
            logger.info(f"Successfully processed {pdf_file}")
            success_count += 1
        else:
            logger.error(f"Failed to process {pdf_file}")
            failure_count += 1
    
    logger.info(f"PDF processing complete. Success: {success_count}, Failures: {failure_count}")
    return failure_count == 0

def initialize_project():
    """Complete system and database initialization"""
    with app.app_context():
        try:
            print("=== Starting Project Initialization ===")
            
            # Step 1: Backup existing databases
            print("\n1. Creating database backups...")
            backup_database()
            
            # Step 2: Drop and recreate all tables
            print("\n2. Recreating database tables...")
            db.drop_all()
            db.drop_all(bind=['audit'])
            db.drop_all(bind=['pdf_parsed'])
            db.create_all()
            db.create_all(bind=['audit'])
            db.create_all(bind=['pdf_parsed'])
            
            # Step 3: Apply database indexes
            print("\n3. Applying database indexes...")
            from apply_indexes import apply_indexes
            apply_indexes()
            
            # Step 4: Create initial users
            print("\n4. Creating initial users...")
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
            nurse = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(nurse)
            db.session.commit()
            
            # Step 5: Initialize settings
            print("\n5. Initializing system settings...")
            settings = {
                'notes_enabled': 'true',
                'timeout_enabled': 'true',
                'timeout_minutes': '60'
            }
            for key, value in settings.items():
                Settings.set_setting(key, value)
            
            # Step 6: Process ward PDF files
            print("\n6. Processing ward PDF files...")
            if process_ward_pdfs():
                print("\n=== Project Initialization Completed Successfully ===")
            else:
                print("\n=== Project Initialization Completed (some PDFs may not have been processed) ===")
            
            print("\nDefault login credentials:")
            print("Admin - username: admin, password: admin123")
            print("Nurse - username: nurse1, password: nurse123")
            
            return True
            
        except Exception as e:
            print(f"\nError during initialization: {str(e)}")
            logger.error(f"Project initialization failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    initialize_project()