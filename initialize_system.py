from app import app, db
from models import (
    User, Settings, TemplateCategory, NoteTemplate, 
    Ward, CareNote, Patient, Note, AuditLog
)
from werkzeug.security import generate_password_hash
from datetime import datetime, UTC
from sqlalchemy import inspect, text
import os
import shutil

def backup_database():
    """Create backup of existing database"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for db_file in ['users.db', 'audit.db']:
        db_path = os.path.join('instance', db_file)
        if os.path.exists(db_path):
            backup_path = os.path.join(backup_dir, f'{db_file}_{timestamp}')
            shutil.copy2(db_path, backup_path)
            print(f"Backed up {db_file} to {backup_path}")

def initialize_system():
    """Initialize the system with essential data"""
    with app.app_context():
        try:
            print("=== Starting System Initialization ===")
            
            # Backup existing databases
            print("\n1. Creating database backups...")
            backup_database()
            
            # Drop and recreate all tables
            print("\n2. Recreating database tables...")
            db.drop_all()
            db.drop_all(bind=['audit'])
            db.create_all()
            db.create_all(bind=['audit'])
            
            # Create initial users
            print("\n3. Creating initial users...")
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
            nurse = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(nurse)
            db.session.commit()
            
            # Confirm admin user creation
            print("\nAdmin user 'admin' created with password 'admin123'")
            
            # Initialize settings
            print("\n4. Initializing system settings...")
            settings = {
                'notes_enabled': 'true',
                'timeout_enabled': 'true',
                'timeout_minutes': '60'
            }
            for key, value in settings.items():
                Settings.set_setting(key, value)
            
            # Process existing ward PDFs
            print("\n5. Processing existing ward PDFs...")
            from deployment_initialize import process_ward_pdfs
            if process_ward_pdfs():
                print("\n=== System Initialization Completed Successfully ===")
            else:
                print("\n=== System Initialization Completed (some PDFs may not have been processed) ===")
            
            print("\nDefault login credentials:")
            print("Admin - username: admin, password: admin123")
            print("Nurse - username: nurse1, password: nurse123")
            
        except Exception as e:
            print(f"\nError during initialization: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    initialize_system()
