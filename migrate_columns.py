from app import app, db
from models import CareNote
from sqlalchemy import inspect

def add_missing_columns():
    """Add missing columns to CareNote table if they don't exist"""
    with app.app_context():
        try:
            # Check if columns exist
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('care_note')]
            
            # Add is_pdf_note column if it doesn't exist
            if 'is_pdf_note' not in columns:
                print("Adding is_pdf_note column to CareNote table...")
                db.engine.execute('ALTER TABLE care_note ADD COLUMN is_pdf_note BOOLEAN DEFAULT 0')
                print("Column added successfully!")
            else:
                print("is_pdf_note column already exists, no migration needed.")
                
            # Add staff column if it doesn't exist
            if 'staff' not in columns:
                print("Adding staff column to CareNote table...")
                db.engine.execute('ALTER TABLE care_note ADD COLUMN staff VARCHAR(100)')
                print("Column added successfully!")
            else:
                print("staff column already exists, no migration needed.")
                
        except Exception as e:
            print(f"Database error: {str(e)}")

if __name__ == "__main__":
    add_missing_columns()
