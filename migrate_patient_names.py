from app import app, db, CareNote
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
import sys

def add_patient_name_column():
    """Add patient_name column to CareNote table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if column exists
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('care_note')]
            
            if 'patient_name' not in columns:
                print("Adding patient_name column to CareNote table...")
                db.engine.execute('ALTER TABLE care_note ADD COLUMN patient_name VARCHAR(100)')
                print("Column added successfully!")
                
                # Update existing notes with patient names
                print("Updating existing notes with patient names...")
                care_notes = CareNote.query.all()
                updated_count = 0
                
                for note in care_notes:
                    # Try to find patient name from the stored ward_id first
                    if note.ward_id and note.ward_id in app.wards_data:
                        ward_info = app.wards_data[note.ward_id]
                        if ward_info.get("patients") and note.patient_id in ward_info["patients"]:
                            note.patient_name = ward_info["patients"][note.patient_id].get("name", "Unknown")
                            updated_count += 1
                            continue
                            
                    # If not found, search through all wards
                    for ward_num, ward_info in app.wards_data.items():
                        if ward_info.get("patients") and note.patient_id in ward_info.get("patients", {}):
                            note.patient_name = ward_info["patients"][note.patient_id].get("name", "Unknown")
                            if not note.ward_id:
                                note.ward_id = ward_num
                            updated_count += 1
                            break
                
                db.session.commit()
                print(f"Updated {updated_count} notes with patient names.")
                print("Migration completed successfully!")
            else:
                print("patient_name column already exists, no migration needed.")
                
        except OperationalError as e:
            print(f"Database error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    add_patient_name_column()
