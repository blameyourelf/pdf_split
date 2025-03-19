from app import app, db
from models import Ward, Patient, Note
from config import Config  # Ensure the Config class is imported

app.config.from_object(Config)  # Apply the configuration

def verify_pdf_parsed_data():
    """Verify that the PDF parsed data has been correctly imported"""
    with app.app_context():
        # Check ward data
        wards = Ward.query.all()
        print(f"Imported {len(wards)} wards")
        
        # Check patient data
        patients = Patient.query.all()
        print(f"Imported {len(patients)} patients")
        
        # Check notes data
        notes = Note.query.all()
        print(f"Imported {len(notes)} notes")
        
        # Verify relationships
        for patient in patients[:5]:  # Check first 5 patients
            print(f"\nPatient {patient.hospital_id}:")
            print(f"Notes count: {len(patient.notes)}")

if __name__ == "__main__":
    verify_pdf_parsed_data()