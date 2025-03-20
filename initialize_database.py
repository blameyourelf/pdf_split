from app import app, db
from models import Ward, Patient, Note, CareNote
import logging
import os
import re
from datetime import datetime
from config import Config
from PyPDF2 import PdfReader

# Fix the invalid escape sequence warning
app.config.from_object(Config)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def extract_patient_data(pdf_path, ward_number):
    """Extract patient and notes data from a single PDF file and save directly to CareNote table"""
    try:
        # Use the working PDF parser
        patient_data = parse_pdf_content(pdf_path)
        total_patients = len(patient_data)
        logger.info(f"Extracted {total_patients} patients from {pdf_path}")

        # Debug information to verify notes are being extracted properly
        for patient_id, info in patient_data.items():
            note_count = len(info.get('care_notes', []))
            if note_count == 0:  # Flag if we have patients with no notes
                logger.warning(f"Patient {patient_id} has no care notes!")
            else:
                logger.info(f"Patient {patient_id} has {note_count} care notes")
                # Log first note as sample
                if note_count > 0:
                    sample_note = info['care_notes'][0]
                    logger.info(f"Sample note: {sample_note['date']} | {sample_note['staff'][:20]} | {sample_note['note'][:30]}...")

        # Batch database operations
        patients_to_add = []
        carenotes_to_add = []  # Changed from notes_to_add
        processed_patients = 0

        for patient_id, info in patient_data.items():
            processed_patients += 1
            if processed_patients % 5 == 0:  # Log progress every 5 patients
                logger.info(f"Processing patient {processed_patients}/{total_patients} in {pdf_path}")

            # Check if patient exists using one query instead of per-patient
            patient = Patient.query.filter_by(hospital_id=patient_id).first()
            if not patient:
                patient = Patient(
                    hospital_id=patient_id,
                    name=info['name'],
                    dob=info['info'].get('DOB', ''),
                    current_ward=ward_number
                )
                patients_to_add.append(patient)
                db.session.add(patient)
                logger.info(f"Added patient: {patient_id} - {info['name']}")
            
            # Batch care note creation (directly to CareNote table)
            for note_data in info['care_notes']:
                timestamp = datetime.strptime(note_data['date'], '%Y-%m-%d %H:%M')
                
                # Only check for existing note if absolutely necessary
                existing_note = CareNote.query.filter_by(
                    patient_id=patient_id,  # Use hospital_id directly
                    timestamp=timestamp,
                    note=note_data['note']
                ).first()

                if not existing_note:
                    # Use the staff_name field that already exists in the model
                    carenote = CareNote(
                        patient_id=patient_id,  # Use hospital_id directly
                        ward_id=ward_number,
                        timestamp=timestamp,
                        staff_name=note_data['staff'],  # Use staff_name field from the model
                        note=note_data['note'],
                        patient_name=info['name'],
                        is_pdf_note=True
                    )
                    carenotes_to_add.append(carenote)

            # Commit in batches to reduce database operations
            if len(carenotes_to_add) >= 100:  # Commit every 100 notes
                db.session.add_all(carenotes_to_add)
                db.session.commit()
                carenotes_to_add = []

        # Final commit for any remaining records
        if carenotes_to_add:
            db.session.add_all(carenotes_to_add)
        db.session.commit()
        
        logger.info(f"Completed processing {pdf_path}")
        return True

    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {str(e)}")
        db.session.rollback()
        return False

def initialize_database():
    """One-time database initialization and PDF import"""
    with app.app_context():
        try:
            # Create all tables in the main database first (which includes care_note table)
            logger.info("Creating database tables in main database...")
            db.create_all()
            
            # Then create tables in the pdf_parsed database
            logger.info("Creating database tables in pdf_parsed database...")
            db.create_all(bind='pdf_parsed')
            
            # Verify that the tables are created in both databases
            # 1. Check main database
            inspector = db.inspect(db.get_engine())
            tables = inspector.get_table_names()
            if 'care_note' not in tables:
                raise Exception("care_note table is not created in the main database.")
                
            # 2. Check pdf_parsed database
            pdf_engine = db.get_engine(app, bind='pdf_parsed')
            pdf_inspector = db.inspect(pdf_engine)
            pdf_tables = pdf_inspector.get_table_names()
            if 'ward' not in pdf_tables or 'patient' not in pdf_tables or 'note' not in pdf_tables:
                raise Exception("Required tables are not created in the pdf_parsed database.")
            
            # Process ward PDFs
            pdf_files = [f for f in os.listdir('.') if f.startswith('ward_') and f.endswith('_records.pdf')]
            logger.info(f"Found {len(pdf_files)} ward PDF files")
            
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
                else:
                    logger.error(f"Failed to process {pdf_file}")
            
            logger.info("Database initialization complete!")
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    initialize_database()