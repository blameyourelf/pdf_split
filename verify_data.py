from app import app, db
from models import Ward, Patient, Note

def verify_data():
    with app.app_context():
        wards = Ward.query.all()
        patients = Patient.query.all()
        notes = Note.query.all()
        
        print(f"Wards: {len(wards)}")
        print(f"Patients: {len(patients)}")
        print(f"Notes: {len(notes)}")
        
        # Sample check
        if patients:
            sample = patients[0]
            print(f"\nSample patient:")
            print(f"ID: {sample.hospital_id}")
            print(f"Name: {sample.name}")
            print(f"Notes: {len(sample.notes)}")

if __name__ == "__main__":
    verify_data()