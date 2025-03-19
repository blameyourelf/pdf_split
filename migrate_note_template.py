from app import app, db
from models import NoteTemplate
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
import sys

def create_note_template_table():
    """Create the note_template table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if table exists
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'note_template' not in tables:
                print("Creating note_template table...")
                # Use the model's metadata to create just this table
                NoteTemplate.__table__.create(db.engine)
                print("Table created successfully!")
                
                # Create some initial templates for users
                create_initial_templates()
                print("Initial templates created!")
            else:
                print("note_template table already exists, no migration needed.")
                
        except OperationalError as e:
            print(f"Database error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            sys.exit(1)

def create_initial_templates():
    """Create some initial note templates for users"""
    templates = [
        {
            'name': 'Medical Clerking',
            'category': 'Medical',
            'content': "Patient presented with:\n\nHistory of presenting complaint:\n\nPast medical history:\n\nExamination findings:\n\nPlan:"
        },
        {
            'name': 'Nursing Admission',
            'category': 'Nursing',
            'content': "Patient admitted for:\n\nObservations on admission:\n- BP:\n- HR:\n- RR:\n- Temp:\n- SpO2:\n\nCurrent medications:\n\nAllergies:\n\nMobility status:"
        },
        {
            'name': 'Surgical Clerking',
            'category': 'Surgical',
            'content': "Patient admitted for:\n\nPre-operative checks:\n- NBM since:\n- Consent signed:\n- Site marked:\n\nPre-operative vitals:\n\nPlan for surgery:"
        },
        {
            'name': 'Daily Ward Round',
            'category': 'Medical',
            'content': "Current status:\n\nVital signs:\n\nAssessment:\n\nPlan:"
        },
        {
            'name': 'Discharge Summary',
            'category': 'Admin',
            'content': "Admission date:\nDischarge date:\n\nDiagnosis:\n\nProcedures/Treatments:\n\nMedications on discharge:\n\nFollow-up plan:"
        }
    ]
    
    for template_data in templates:
        template = NoteTemplate(
            name=template_data['name'],
            category=template_data['category'],
            content=template_data['content'],
            is_active=True
        )
        db.session.add(template)
    
    db.session.commit()

if __name__ == "__main__":
    create_note_template_table()
