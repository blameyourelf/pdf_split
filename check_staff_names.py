from app import app, db, CareNote
import sys

def check_staff_names():
    """Check if staff names are properly stored in the CareNote table"""
    with app.app_context():
        # Get total count
        total_notes = CareNote.query.count()
        print(f"Total CareNotes in database: {total_notes}")
        
        # Count notes with staff_name set
        notes_with_staff = CareNote.query.filter(CareNote.staff_name.isnot(None)).count()
        print(f"Notes with staff_name set: {notes_with_staff}")
        
        # Count notes with empty staff_name
        empty_staff = CareNote.query.filter(CareNote.staff_name == '').count()
        print(f"Notes with empty staff_name: {empty_staff}")
        
        # Count notes with NULL staff_name
        null_staff = CareNote.query.filter(CareNote.staff_name.is_(None)).count()
        print(f"Notes with NULL staff_name: {null_staff}")
        
        # Sample 5 notes to check their staff_name values
        print("\nSample notes:")
        sample_notes = CareNote.query.limit(5).all()
        for i, note in enumerate(sample_notes, 1):
            print(f"Note {i}:")
            print(f"  Patient: {note.patient_name}")
            print(f"  Staff: '{note.staff_name}'")
            print(f"  Timestamp: {note.timestamp}")
            print(f"  Note: {note.note[:50]}...")

if __name__ == "__main__":
    check_staff_names()