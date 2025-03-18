import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, CareNote
from models import Patient, Note, Ward

def verify_migration():
    """Verify that the migration was successful"""
    with app.app_context():
        # Test 1: Check ward data migration
        wards = Ward.query.all()
        print(f"Migrated {len(wards)} wards")
        
        # Test 2: Check patient data migration
        patients = Patient.query.all()
        print(f"Migrated {len(patients)} patients")
        
        # Test 3: Check notes migration
        old_notes = CareNote.query.count()
        new_notes = Note.query.count()
        print(f"Original notes: {old_notes}")
        print(f"Migrated notes: {new_notes}")
        
        # Test 4: Verify relationships
        for patient in patients[:5]:  # Check first 5 patients
            print(f"\nPatient {patient.hospital_id}:")
            print(f"Notes count: {len(patient.notes)}")
        
        return all([
            len(wards) > 0,
            len(patients) > 0,
            new_notes >= old_notes
        ])

if __name__ == "__main__":
    success = verify_migration()
    print(f"\nMigration verification {'successful' if success else 'failed'}")
