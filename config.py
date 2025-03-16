import os
from datetime import timedelta

class Config:
    # Secret keys and sensitive info
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-key-change-in-production'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///users.db'
    SQLALCHEMY_BINDS = {
        'audit': os.environ.get('AUDIT_DATABASE_URL') or 'sqlite:///audit.db'
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # Session settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    
    # PDF directory
    PDF_DIRECTORY = os.environ.get('PDF_DIRECTORY') or '.'
    
    # Logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
