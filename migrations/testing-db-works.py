import sys
import os
from datetime import datetime

# Add parent directory to Python path - Fix the path handling
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Now we can import from the parent directory
from app import app, db
from models import Ward, Patient, Note, CareNote

def verify_note_migration():
    """Verify that notes have been properly migrated to the database"""
    with app.app_context():
        try:
            # Count notes in different tables
            total_care_notes = CareNote.query.count()
            total_notes = Note.query.count()
            pdf_notes = Note.query.filter_by(is_pdf_note=True).count()
            manual_notes = CareNote.query.filter_by(is_pdf_note=False).count() if hasattr(CareNote, 'is_pdf_note') else 0
            
            # Count patients with notes
            patients_with_notes = db.session.query(Patient.id).join(Note).distinct().count()
            total_patients = Patient.query.count()
            
            # Count wards with notes
            wards_with_notes = db.session.query(Ward.ward_number).join(
                Note, Ward.ward_number == Note.ward_id
            ).distinct().count()
            total_wards = Ward.query.count()
            
            # Verify content of some notes (sample check)
            sample_notes = Note.query.limit(5).all()
            
            print("=== Note Migration Verification ===")
            print(f"Total patients: {total_patients}")
            print(f"Patients with notes: {patients_with_notes}")
            print(f"Total wards: {total_wards}")
            print(f"Wards with notes: {wards_with_notes}")
            print(f"Care notes in database: {total_care_notes}")
            print(f"Notes in database: {total_notes}")
            print(f"PDF-extracted notes: {pdf_notes}")
            print(f"Manual notes: {manual_notes}")
            
            print("\nSample notes:")
            for note in sample_notes:
                print(f"- Patient: {note.patient.name if note.patient else 'Unknown'}")
                print(f"  Ward: {note.ward_id}")
                print(f"  Date: {note.timestamp}")
                print(f"  Note text: {note.note_text[:50]}..." if len(note.note_text) > 50 else note.note_text)
                print()
                
            return total_notes > 0
            
        except Exception as e:
            print(f"Verification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = verify_note_migration()
    print(f"\nVerification {'successful' if success else 'failed'}")
    sys.exit(0 if success else 1)