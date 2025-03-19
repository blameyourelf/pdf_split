from app import app, db, extract_patient_info
from models import Ward, Patient
import os
from datetime import datetime
from sqlalchemy import text
import re

def process_ward_pdfs():
    """Process existing ward PDFs and update database tables"""
    with app.app_context():
        try:
            print("Processing existing ward PDFs...")
            
            # Get list of existing ward PDFs
            ward_files = [f for f in os.listdir('.') if f.startswith('ward_') and f.endswith('_records.pdf')]
            
            if not ward_files:
                print("No ward PDF files found in current directory")
                return False
            
            print(f"Found {len(ward_files)} ward PDF files")
            
            # Process each ward file
            for pdf_filename in ward_files:
                # Extract ward number/name from filename (between 'ward_' and '_records.pdf')
                ward_part = pdf_filename[5:-12]  # Remove 'ward_' and '_records.pdf'
                
                # Determine display name
                if ward_part.startswith('Long_'):
                    display_name = f"Long {ward_part[5:]}"
                elif ward_part.isdigit():
                    display_name = f"Ward {ward_part}"
                else:
                    display_name = ward_part
                
                print(f"\nProcessing {pdf_filename}...")
                
                # Create or update ward record
                ward = Ward.query.filter_by(ward_number=ward_part).first()
                if not ward:
                    ward = Ward(
                        ward_number=ward_part,
                        display_name=display_name,
                        pdf_file=pdf_filename,
                        last_updated=datetime.utcnow()
                    )
                    db.session.add(ward)
                    print(f"Created new ward record: {display_name}")
                else:
                    ward.pdf_file = pdf_filename
                    ward.last_updated = datetime.utcnow()
                    print(f"Updated existing ward record: {display_name}")
                
                # Extract patient data from PDF
                patient_data = extract_patient_info(pdf_filename)
                print(f"Found {len(patient_data)} patients in {pdf_filename}")
                
                # Create or update patient records
                for patient_id, info in patient_data.items():
                    existing_patient = Patient.query.filter_by(hospital_id=patient_id).first()
                    
                    if not existing_patient:
                        # Create new patient record
                        patient = Patient(
                            hospital_id=patient_id,
                            name=info.get('name', 'Unknown'),
                            dob=info.get('info', {}).get('DOB', ''),
                            current_ward=ward_part,
                            pdf_file=pdf_filename,
                            is_active=True
                        )
                        db.session.add(patient)
                        print(f"Created new patient record: {patient_id}")
                    else:
                        # Update existing patient record
                        existing_patient.name = info.get('name', 'Unknown')
                        existing_patient.dob = info.get('info', {}).get('DOB', '')
                        existing_patient.current_ward = ward_part
                        existing_patient.pdf_file = pdf_filename
                        existing_patient.is_active = True
                        print(f"Updated existing patient record: {patient_id}")
                
                db.session.commit()
            
            print("\nAll ward PDFs processed successfully!")
            return True
            
        except Exception as e:
            print(f"Error processing ward PDFs: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    process_ward_pdfs()
