import os
import sys
import shutil
from datetime import datetime
from sqlalchemy import inspect

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Settings
from werkzeug.security import generate_password_hash

def backup_databases():
    """Create backups of existing databases before deletion"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Backup main database
    if os.path.exists('instance/users.db'):
        backup_path = os.path.join(backup_dir, f'users_{timestamp}.db')
        shutil.copy2('instance/users.db', backup_path)
        print(f"Backed up main database to {backup_path}")
    
    # Backup audit database
    if os.path.exists('instance/audit.db'):
        backup_path = os.path.join(backup_dir, f'audit_{timestamp}.db')
        shutil.copy2('instance/audit.db', backup_path)
        print(f"Backed up audit database to {backup_path}")
    
    return True

def delete_databases():
    """Delete existing database files"""
    try:
        # Remove main database
        if os.path.exists('instance/users.db'):
            os.remove('instance/users.db')
            print("Deleted main database file")
        
        # Remove audit database
        if os.path.exists('instance/audit.db'):
            os.remove('instance/audit.db')
            print("Deleted audit database file")
            
        return True
    except Exception as e:
        print(f"Error deleting database files: {str(e)}")
        return False

def create_new_databases():
    """Create new databases with initial schema and default data"""
    with app.app_context():
        try:
            # Drop all existing tables first
            print("Dropping existing tables...")
            db.drop_all()
            db.drop_all(bind=['audit'])
            
            # Create fresh tables
            print("Creating database tables...")
            db.create_all()
            db.create_all(bind=['audit'])
            
            # Ensure session is clean
            db.session.remove()
            
            # Create users in a new session
            print("Creating default admin user...")
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
            print("Creating test user...")
            test_user = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(test_user)
            db.session.commit()
            
            # Create settings in a separate transaction
            print("Creating initial settings...")
            Settings.set_setting('notes_enabled', 'true')
            Settings.set_setting('timeout_enabled', 'true')
            Settings.set_setting('timeout_minutes', '60')
            
            # Verify tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Created {len(tables)} tables in main database: {', '.join(tables)}")
            
            return True
            
        except Exception as e:
            print(f"Error creating databases: {str(e)}")
            db.session.rollback()
            return False

def reset_databases():
    """Main function to reset all databases"""
    print("=== Database Reset Process Starting ===\n")
    
    # Step 1: Create backups
    print("\n--- Step 1: Creating Backups ---")
    if not backup_databases():
        print("Failed to create backups. Aborting reset process.")
        return False
    
    # Step 2: Delete existing databases
    print("\n--- Step 2: Deleting Existing Databases ---")
    if not delete_databases():
        print("Failed to delete existing databases. Aborting reset process.")
        return False
    
    # Step 3: Create new databases
    print("\n--- Step 3: Creating New Databases ---")
    if not create_new_databases():
        print("Failed to create new databases.")
        return False
    
    print("\n=== Database Reset Completed Successfully ===")
    print("You can now run additional migrations if needed.")
    return True

if __name__ == "__main__":
    # Ask for confirmation before proceeding
    response = input("This will reset ALL databases and lose all data. Are you sure you want to proceed? (y/n): ")
    if response.lower() == 'y':
        reset_databases()
    else:
        print("Database reset cancelled.")
