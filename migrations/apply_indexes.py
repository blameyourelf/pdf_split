import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Patient, CareNote, User, AuditLog, Ward, RecentlyViewedPatient, Settings, NoteTemplate, TemplateCategory

def apply_indexes():
    """Apply all indexes to the correct databases based on bind_key configuration"""
    print("Starting index migration...")
    
    with app.app_context():
        # Group 1: Main database indexes
        main_db_indexes = [
            # User table indexes
            ('CREATE INDEX IF NOT EXISTS idx_user_username ON user (username)'),
            ('CREATE INDEX IF NOT EXISTS idx_user_role ON user (role)'),
            
            # Care Note indexes - these appear to be in the main DB
            ('CREATE INDEX IF NOT EXISTS idx_carenote_patient_id ON care_note (patient_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_timestamp ON care_note (timestamp DESC)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_user_id ON care_note (user_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_ward_id ON care_note (ward_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_carenote_is_pdf_note ON care_note (is_pdf_note)'),
            
            # Recently viewed patients
            ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_user_id ON recently_viewed_patient (user_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_timestamp ON recently_viewed_patient (viewed_at DESC)'),
            
            # Settings
            ('CREATE INDEX IF NOT EXISTS idx_settings_key ON settings (key)'),
            
            # Note Templates
            ('CREATE INDEX IF NOT EXISTS idx_note_template_category ON note_template (category_id)'),
            ('CREATE INDEX IF NOT EXISTS idx_note_template_active ON note_template (is_active)')
        ]
        
        # Apply main DB indexes
        for index_sql in main_db_indexes:
            try:
                print(f"Applying to main DB: {index_sql}")
                db.session.execute(index_sql)
                db.session.commit()
            except Exception as e:
                print(f"Error applying index: {str(e)}")
                db.session.rollback()
        
        # Group 2: pdf_parsed database indexes - need to use the correct bind key
        # We need to use a different approach to create indexes in the pdf_parsed database
        
        # This approach uses SQLAlchemy's bind feature
        try:
            pdf_parsed_engine = db.get_engine(app, 'pdf_parsed')
            pdf_parsed_indexes = [
                ('CREATE INDEX IF NOT EXISTS idx_patient_hospital_id ON patient (hospital_id)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_current_ward ON patient (current_ward)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_is_active ON patient (is_active)'),
                ('CREATE INDEX IF NOT EXISTS idx_patient_name ON patient (name)'),
                ('CREATE INDEX IF NOT EXISTS idx_ward_ward_number ON ward (ward_number)')
            ]
            
            for index_sql in pdf_parsed_indexes:
                try:
                    print(f"Applying to pdf_parsed DB: {index_sql}")
                    pdf_parsed_engine.execute(index_sql)
                except Exception as e:
                    print(f"Error applying index to pdf_parsed DB: {str(e)}")
        except Exception as e:
            print(f"Error accessing pdf_parsed database: {str(e)}")
            
        # Group 3: audit database indexes
        try:
            audit_engine = db.get_engine(app, 'audit')
            audit_indexes = [
                ('CREATE INDEX IF NOT EXISTS idx_auditlog_timestamp ON audit_log (timestamp DESC)'),
                ('CREATE INDEX IF NOT EXISTS idx_auditlog_user_id ON audit_log (user_id)')
            ]
            
            for index_sql in audit_indexes:
                try:
                    print(f"Applying to audit DB: {index_sql}")
                    audit_engine.execute(index_sql)
                except Exception as e:
                    print(f"Error applying index to audit DB: {str(e)}")
        except Exception as e:
            print(f"Error accessing audit database: {str(e)}")
    
    print("Index migration completed!")

if __name__ == "__main__":
    apply_indexes()