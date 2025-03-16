from app import app, db
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
import sys

def add_ward_id_column():
    """Add ward_id column to CareNote table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if column exists
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('care_note')]
            
            if 'ward_id' not in columns:
                print("Adding ward_id column to CareNote table...")
                db.engine.execute('ALTER TABLE care_note ADD COLUMN ward_id VARCHAR(50)')
                print("Column added successfully!")
                
                # Update existing notes with ward info
                from app import CareNote, wards_data
                
                print("Updating existing notes with ward information...")
                care_notes = CareNote.query.all()
                updated_count = 0
                
                for note in care_notes:
                    # Try to find ward for this patient
                    found_ward = False
                    for ward_num, ward_info in wards_data.items():
                        if ward_info.get("patients") and note.patient_id in ward_info.get("patients", {}):
                            note.ward_id = ward_num
                            found_ward = True
                            updated_count += 1
                            break
                
                db.session.commit()
                print(f"Updated {updated_count} notes with ward information.")
                print("Migration completed successfully!")
            else:
                print("ward_id column already exists, no migration needed.")
                
        except OperationalError as e:
            print(f"Database error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    add_ward_id_column()
