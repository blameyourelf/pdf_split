from app import app, db
from models import Ward, Patient, Note
from PyPDF2 import PdfReader
import logging
import os
import re
from datetime import datetime
from config import Config  # Ensure the Config class is imported

app.config.from_object(Config)  # Apply the configuration

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_patient_data(pdf_path, ward_number):
    """Extract patient and notes data from a single PDF file"""
    try:
        reader = PdfReader(pdf_path)
        current_patient = None
        
        for page in reader.pages:
            text = page.extract_text()
            logger.debug(f"Extracted text from page: {text[:100]}...")  # Log the first 100 characters of the extracted text
            
            # Find patient headers (using case‑insensitive matching)
            patient_matches = re.finditer(
                r'(\d{10})\s+((?!Name\b)[A-Za-z\s,\-]+)(?:\s+DOB:\s+(\d{2}/\d{2}/\d{4}))?',
                text,
                flags=re.IGNORECASE
            )
            
            for match in patient_matches:
                hospital_id, name, dob = match.groups()
                logger.debug(f"Found patient match: hospital_id={hospital_id}, name={name}, dob={dob}")  # Log the matched patient details
                # Skip header rows if the name equals "Name"
                if name.strip().lower() == "name":
                    logger.debug("Skipping header row")
                    continue
                # Create or update patient record
                patient = Patient.query.filter_by(hospital_id=hospital_id).first()
                if not patient:
                    patient = Patient(
                        hospital_id=hospital_id,
                        name=name.strip(),
                        dob=dob,
                        current_ward=ward_number
                    )
                    db.session.add(patient)
                    logger.info(f"Added patient: {hospital_id} - {name.strip()}")
                else:
                    logger.debug(f"Patient already exists: {hospital_id} - {name.strip()}")
                current_patient = patient

            # Extract notes if we're in a notes section
            if "Continuous Care Notes" in text:
                notes_section = text.split("Continuous Care Notes")[1]
                for line in notes_section.split('\n'):
                    if current_patient and re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', line):
                        try:
                            # Parse note line
                            date_str = line[:16]  # YYYY-MM-DD HH:MM
                            remaining = line[16:].strip()
                            parts = [p.strip() for p in re.split(r'\s{2,}', remaining)]
                            if len(parts) >= 2:
                                note = Note(
                                    patient=current_patient,
                                    ward_id=ward_number,
                                    timestamp=datetime.strptime(date_str, '%Y-%m-%d %H:%M'),
                                    staff_name=parts[0],
                                    note_text=' '.join(parts[1:]),
                                    is_pdf_note=True
                                )
                                db.session.add(note)
                                logger.info(f"Added note for patient {current_patient.hospital_id}: {line[:50]}...")
                            else:
                                logger.debug(f"Skipping incomplete note line: {line}")
                        except Exception as e:
                            logger.error(f"Error parsing note: {line[:50]}... Error: {str(e)}")

        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {str(e)}")
        db.session.rollback()
        return False

def initialize_database():
    """One-time database initialization and PDF import"""
    with app.app_context():
        try:
            # Bind to the new database for PDF parsed information
            engine = db.get_engine(app, bind='pdf_parsed')
            
            # Create all tables
            logger.info("Creating database tables...")
            db.create_all(bind='pdf_parsed')
            
            # Verify that the tables are created
            inspector = db.inspect(engine)
            tables = inspector.get_table_names()
            if 'ward' not in tables or 'patient' not in tables or 'note' not in tables:
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