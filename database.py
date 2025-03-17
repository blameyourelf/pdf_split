import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, desc, inspect
from sqlalchemy.orm import scoped_session, sessionmaker

# Initialize SQLAlchemy without binding to app yet
db = SQLAlchemy()

def init_app(app):
    """Initialize the database with the app"""
    # Ensure instance path exists
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    
    # Database configuration 
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'users.db')
    app.config['SQLALCHEMY_BINDS'] = {
        'audit': 'sqlite:///' + os.path.join(app.instance_path, 'audit.db')
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'connect_args': {'check_same_thread': False}
    }
    
    # Initialize database with app
    db.init_app(app)
    
    # Create database directory if it doesn't exist
    db_dir = os.path.dirname(os.path.join(app.instance_path, 'users.db'))
    os.makedirs(db_dir, exist_ok=True)
