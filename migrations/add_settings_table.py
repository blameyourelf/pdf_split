import os
import sys

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, Settings

def add_settings_table():
    """Create settings table and add initial notes_enabled setting"""
    with app.app_context():
        db.create_all()  # This will create the settings table if it doesn't exist
        
        # Add initial notes_enabled setting if it doesn't exist
        if not Settings.query.filter_by(key='notes_enabled').first():
            setting = Settings(key='notes_enabled', value='true')
            db.session.add(setting)
            db.session.commit()
            print("Added initial notes_enabled setting")
        else:
            print("notes_enabled setting already exists")

if __name__ == "__main__":
    add_settings_table()
