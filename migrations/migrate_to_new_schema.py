import sys
import os
from datetime import datetime
import logging
from PyPDF2 import PdfReader
import re

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Ward, Patient, Note

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_patient_info(pdf_path):
    """Extract patient information from PDF files"""
    logger.info(f"Extracting patient information from {pdf_path}")
    
    try:
        # Create a PDF reader object
        reader = PdfReader(pdf_path)
        
        # Store patient data
        patients = {}
        current_patient_id = None
        
        # Process each page for patient headers
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            logger.info(f"Processing page {page_num+1}, text length: {len(text)}")
            
            # Find patient records
            # This regex pattern needs to match how patient IDs appear in your PDFs
            patient_pattern = r'(\d{10})\s+([A-Za-z\s,\-]+)(?:\s+DOB:\s+(\d{2}/\d{2}/\d{4}))?'
            
            for match in re.finditer(patient_pattern, text):
                patient_id, name, dob = match.groups()
                current_patient_id = patient_id  # Track current patient for care notes
                
                # Add patient to our dictionary if not already there
                if patient_id not in patients:
                    patients[patient_id] = {
                        'name': name.strip(),
                        'info': {
                            'DOB': dob if dob else 'Unknown'
                        },
                        'care_notes': []
                    }
                    
                    logger.info(f"Found patient: {patient_id} - {name.strip()}")
            
            # Now extract care notes if we found any patients
            if current_patient_id and "Continuous Care Notes" in text:
                # Find the care notes section
                sections = text.split("Continuous Care Notes")
                if len(sections) > 1:
                    notes_section = sections[1]
                    lines = notes_section.split('\n')
                    
                    # Look for notes after header row
                    in_notes_table = False
                    for line in lines:
                        if "Date & Time" in line and "Staff Member" in line and "Notes" in line:
                            in_notes_table = True
                            continue
                        
                        if in_notes_table and line.strip():
                            # Try to match date pattern at start of line (YYYY-MM-DD HH:MM)
                            date_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
                            if date_match:
                                try:
                                    date_str = date_match.group(1)
                                    remaining = line[len(date_str):].strip()
                                    
                                    # Split remaining text to get staff and note
                                    parts = [p for p in re.split(r'\s{2,}', remaining) if p.strip()]
                                    
                                    if len(parts) >= 2:
                                        staff = parts[0].strip()
                                        note = ' '.join(parts[1:]).strip()
                                        
                                        # Add note to current patient
                                        if current_patient_id in patients:
                                            patients[current_patient_id]['care_notes'].append({
                                                'date': date_str,
                                                'staff': staff,
                                                'note': note
                                            })
                                            logger.debug(f"Added note for {current_patient_id}: {date_str}")
                                except Exception as e:
                                    logger.error(f"Error parsing note line: {line[:50]}... Error: {str(e)}")
        
        # Log summary of extracted notes
        for patient_id, data in patients.items():
            logger.info(f"Patient {patient_id} has {len(data.get('care_notes', []))} care notes")
            
        logger.info(f"Extracted {len(patients)} patients from {pdf_path}")
        return patients
        
    except Exception as e:
        logger.error(f"Error extracting data from {pdf_path}: {str(e)}")
        return {}

def migrate_schema():
    """Migrate data to new schema with detailed logging"""
    with app.app_context():
        try:
            logger.info("Starting migration...")
            
            # Create new tables if they don't exist
            db.create_all()
            
            # Step 1: Migrate ward data
            logger.info("Migrating ward data...")
            from app import wards_data
            
            for ward_num, ward_info in wards_data.items():
                existing_ward = Ward.query.filter_by(ward_number=ward_num).first()
                if not existing_ward:
                    ward = Ward(
                        ward_number=ward_num,
                        display_name=ward_info.get('display_name', ward_num),
                        pdf_file=ward_info.get('filename'),
                        last_updated=datetime.utcnow()
                    )
                    db.session.add(ward)
            db.session.commit()
            logger.info("Ward data migration completed")
            
            # Get all wards with PDF files
            wards = Ward.query.filter(Ward.pdf_file.isnot(None)).all()
            logger.info(f"Found {len(wards)} wards with PDF files")
            
            for ward in wards:
                logger.info(f"Processing ward {ward.ward_number} with file {ward.pdf_file}")
                if hasattr(ward, 'pdf_file') and ward.pdf_file:
                    patient_data = extract_patient_info(ward.pdf_file)
                    logger.info(f"Extracted {len(patient_data)} patients from {ward.pdf_file}")
                    
                    for hospital_id, info in patient_data.items():
                        if not Patient.query.filter_by(hospital_id=hospital_id).first():
                            patient = Patient(
                                hospital_id=hospital_id,
                                name=info.get('name', 'Unknown'),
                                dob=info['info'].get('DOB'),
                                current_ward=ward.ward_number,
                                pdf_file=ward.pdf_file
                            )
                            db.session.add(patient)
                            
                            # Add PDF notes
                            for note_data in info.get('care_notes', []):
                                note = Note(
                                    patient=patient,
                                    staff_name=note_data.get('staff', 'Unknown'),
                                    note_text=note_data.get('note', ''),
                                    ward_id=ward.ward_number,
                                    timestamp=datetime.strptime(note_data['date'], '%Y-%m-%d %H:%M'),
                                    is_pdf_note=True
                                )
                                db.session.add(note)
                    db.session.commit()
            logger.info("Patient and notes migration completed")
            
            logger.info("Migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_schema()
