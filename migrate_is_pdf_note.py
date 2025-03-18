from app import app, db, CareNote
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
import sys

def add_is_pdf_note_column():
    """Add is_pdf_note column to CareNote table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if column exists
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('care_note')]
            
            if 'is_pdf_note' not in columns:
                print("Adding is_pdf_note column to CareNote table...")
                db.engine.execute('ALTER TABLE care_note ADD COLUMN is_pdf_note BOOLEAN DEFAULT FALSE')
                print("Column added successfully!")
                
                # Set all existing notes to False since they were manually added
                print("Setting all existing notes as manually added...")
                db.session.execute('UPDATE care_note SET is_pdf_note = FALSE')
                db.session.commit()
                print("Migration completed successfully!")
            else:
                print("is_pdf_note column already exists, no migration needed.")
                
        except OperationalError as e:
            print(f"Database error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    add_is_pdf_note_column()
