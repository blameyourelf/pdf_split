import sys
import os
from datetime import datetime

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, User, Patient, Note, Ward

def migrate_schema():
    """Migrate data to new schema"""
    with app.app_context():
        try:
            print("Starting migration...")
            
            # Create new tables if they don't exist
            db.create_all()
            
            # Step 1: Migrate ward data
            print("Migrating ward data...")
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
            print("Ward data migration completed")
            
            # Step 2: Migrate patient data
            print("Migrating patient data...")
            from app import extract_patient_info
            
            for ward in Ward.query.all():
                if os.path.exists(ward.pdf_file):
                    patient_data = extract_patient_info(ward.pdf_file)
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
            print("Patient and notes migration completed")
            
            print("Migration completed successfully!")
            return True
            
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    migrate_schema()
