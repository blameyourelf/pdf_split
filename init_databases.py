import os
import sys
from app import app, db, User
from werkzeug.security import generate_password_hash

def init_databases():
    # Create instance directory if it doesn't exist
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
        print(f"Created instance directory at {instance_path}")

    # Initialize databases
    with app.app_context():
        try:
            # Create all databases
            db.create_all()
            print("Created main database tables")
            
            db.create_all(bind=['audit'])
            print("Created audit database tables")
            
            # Create default admin user if not exists
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    password_hash=generate_password_hash('admin123'),
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("Created default admin user")
            
            print("Database initialization complete!")
            
        except Exception as e:
            print(f"Error initializing databases: {e}")
            sys.exit(1)

if __name__ == "__main__":
    init_databases()
