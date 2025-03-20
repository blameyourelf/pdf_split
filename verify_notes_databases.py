from app import app, db, CareNote
from models import Note
import sys

def verify_notes_databases():
    """Check notes in both databases to see which one has data"""
    with app.app_context():
        # Check pdf_parsed database (Notes table)
        try:
            note_count = Note.query.count()
            if note_count > 0:
                sample_notes = Note.query.limit(3).all()
                print(f"PDF Parsed DB: Found {note_count} notes in Notes table")
                print("\nSample Notes:")
                for note in sample_notes:
                    print(f"- Patient: {note.patient.name if note.patient else 'Unknown'}")
                    print(f"- Text: {note.note_text[:50]}...")
                    print(f"- Date: {note.timestamp}")
                    print("---")
            else:
                print("PDF Parsed DB: Notes table is empty")
        except Exception as e:
            print(f"Error checking Notes table: {str(e)}")
        
        # Check main database (CareNotes table)
        try:
            carenote_count = CareNote.query.count()
            if carenote_count > 0:
                sample_notes = CareNote.query.limit(3).all()
                print(f"\nMain DB: Found {carenote_count} notes in CareNote table")
                print("\nSample CareNotes:")
                for note in sample_notes:
                    print(f"- Patient: {note.patient_name or 'Unknown'} (ID: {note.patient_id})")
                    print(f"- Text: {note.note[:50]}...")
                    print(f"- Date: {note.timestamp}")
                    print(f"- Staff: {note.staff_name or 'Unknown'}")
                    print("---")
            else:
                print("\nMain DB: CareNote table is empty")
        except Exception as e:
            print(f"Error checking CareNote table: {str(e)}")

if __name__ == "__main__":
    verify_notes_databases()