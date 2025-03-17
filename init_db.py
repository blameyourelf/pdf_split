"""
Database initialization script for the PDF Split application.
Ensures all database tables are created before the application starts.
"""
import os
from werkzeug.security import generate_password_hash
from flask import Flask
from database import db

def init_database(app):
    """Initialize the database with default data."""
    with app.app_context():
        # Initialize models first
        from models import init_db
        init_db(db)
        
        # Now import the properly initialized models
        from models import User, Ward, Patient, Settings

        # Create default admin user if not exists
        try:
            # Check if admin user exists
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    password_hash=generate_password_hash('admin123'),
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("Created default admin user")
            
            # Check if test user exists
            nurse = User.query.filter_by(username='nurse1').first()
            if not nurse:
                nurse = User(
                    username='nurse1',
                    password_hash=generate_password_hash('nurse123'),
                    role='user'
                )
                db.session.add(nurse)
                db.session.commit()
                print("Created default nurse user")
                
            # Additional initialization if needed
            
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing database: {e}")
            raise

if __name__ == "__main__":
    # Create Flask application with proper configuration
    app = Flask(__name__)
    
    # Ensure instance path exists
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'users.db')
    app.config['SQLALCHEMY_BINDS'] = {
        'audit': 'sqlite:///' + os.path.join(app.instance_path, 'audit.db')
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    from database import init_app
    init_app(app)
    
    # Run initialization
    init_database(app)
