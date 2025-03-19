from app import app, db, CareNote, Patient, Ward
from datetime import datetime

def check_database_state():
    with app.app_context():
        # Check Care Notes
        total_notes = CareNote.query.count()
        print(f"Total Care Notes in database: {total_notes}")
        
        # Sample a few notes if they exist
        if total_notes > 0:
            sample_notes = CareNote.query.limit(5).all()
            print("\nSample Care Notes:")
            for note in sample_notes:
                print(f"Patient ID: {note.patient_id}")
                print(f"Note: {note.note[:100]}...")
                print(f"Timestamp: {note.timestamp}")
                print("---")
        
        # Check Patients
        total_patients = Patient.query.count()
        print(f"\nTotal Patients: {total_patients}")
        
        # Check Wards
        total_wards = Ward.query.count()
        print(f"Total Wards: {total_wards}")

if __name__ == "__main__":
    check_database_state()