from app import app, db, Note, Patient, Ward
from datetime import datetime

def check_notes_table():
    with app.app_context():
        # Check Notes
        total_notes = Note.query.count()
        print(f"Total Notes in database: {total_notes}")
        
        # Sample a few notes if they exist
        if total_notes > 0:
            sample_notes = Note.query.limit(5).all()
            print("\nSample Notes:")
            for note in sample_notes:
                print(f"Patient ID: {note.patient_id}")
                print(f"Note Text: {note.text[:100] if note.text else 'No text'}...")
                print(f"Created At: {note.timestamp}")
                # Print all attributes of the note object
                print("All attributes:", vars(note))
                print("---")
        else:
            print("\nNo notes found in the Notes table")
            
        # Get total count of notes per patient
        patient_counts = db.session.query(Note.patient_id, db.func.count(Note.id)).\
            group_by(Note.patient_id).all()
        if patient_counts:
            print("\nNotes distribution by patient:")
            for patient_id, count in patient_counts:
                print(f"Patient {patient_id}: {count} notes")

if __name__ == "__main__":
    check_notes_table()