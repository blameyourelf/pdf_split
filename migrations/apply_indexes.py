import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Patient, CareNote, User, AuditLog, Ward, RecentlyViewedPatient

# List of important indexes to create
indexes = [
    # Patient indexes - for faster patient lookups
    ('CREATE INDEX IF NOT EXISTS idx_patient_hospital_id ON patient (hospital_id)'),
    ('CREATE INDEX IF NOT EXISTS idx_patient_current_ward ON patient (current_ward)'),
    ('CREATE INDEX IF NOT EXISTS idx_patient_is_active ON patient (is_active)'),
    ('CREATE INDEX IF NOT EXISTS idx_patient_name ON patient (name)'),
    
    # CareNote indexes - for faster note retrieval
    ('CREATE INDEX IF NOT EXISTS idx_carenote_patient_id ON care_note (patient_id)'),
    ('CREATE INDEX IF NOT EXISTS idx_carenote_timestamp ON care_note (timestamp DESC)'),
    ('CREATE INDEX IF NOT EXISTS idx_carenote_user_id ON care_note (user_id)'),
    ('CREATE INDEX IF NOT EXISTS idx_carenote_ward_id ON care_note (ward_id)'),
    ('CREATE INDEX IF NOT EXISTS idx_carenote_is_pdf_note ON care_note (is_pdf_note)'),
    
    # User indexes
    ('CREATE INDEX IF NOT EXISTS idx_user_username ON user (username)'),
    ('CREATE INDEX IF NOT EXISTS idx_user_role ON user (role)'),
    
    # AuditLog indexes
    ('CREATE INDEX IF NOT EXISTS idx_auditlog_timestamp ON audit_log (timestamp DESC)'),
    ('CREATE INDEX IF NOT EXISTS idx_auditlog_user_id ON audit_log (user_id)'),
    
    # Ward indexes
    ('CREATE INDEX IF NOT EXISTS idx_ward_ward_number ON ward (ward_number)'),
    
    # RecentlyViewedPatient indexes
    ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_user_id ON recently_viewed_patient (user_id)'),
    ('CREATE INDEX IF NOT EXISTS idx_recently_viewed_timestamp ON recently_viewed_patient (viewed_at DESC)')
]

def apply_indexes():
    """Apply all indexes to the database"""
    print("Starting index migration...")
    
    with app.app_context():
        for index_sql in indexes:
            try:
                print(f"Applying: {index_sql}")
                db.session.execute(index_sql)
                db.session.commit()
            except Exception as e:
                print(f"Error applying index: {str(e)}")
                db.session.rollback()
    
    print("Index migration completed!")

if __name__ == "__main__":
    apply_indexes()