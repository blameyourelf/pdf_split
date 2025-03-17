from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.orm import relationship

# Initialize db as None - will be properly set through init_db
db = None
User = None
Ward = None
Patient = None 
AuditLog = None
RecentlyViewedPatient = None
CareNote = None
Settings = None

def init_db(database):
    """Initialize the database for models"""
    global db, User, Ward, Patient, AuditLog, RecentlyViewedPatient, CareNote, Settings
    db = database
    
    # Define models AFTER db is initialized
    class User(UserMixin, db.Model):
        __tablename__ = 'user'
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        password_hash = db.Column(db.String(200), nullable=False)
        role = db.Column(db.String(20), default='user')
        default_ward = db.Column(db.String(50))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class Ward(db.Model):
        """Model for ward information"""
        __tablename__ = 'ward'
        id = db.Column(db.String(50), primary_key=True)
        display_name = db.Column(db.String(100))
        filename = db.Column(db.String(255))
        last_updated = db.Column(db.DateTime, default=datetime.utcnow)
        patients = relationship('Patient', backref='ward', lazy=True)

    class Patient(db.Model):
        """Model for patient information"""
        __tablename__ = 'patient'
        id = db.Column(db.String(50), primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        ward_id = db.Column(db.String(50), db.ForeignKey('ward.id'), nullable=False)
        additional_info = db.Column(db.Text)
        vitals = db.Column(db.Text)
        last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    class AuditLog(db.Model):
        __tablename__ = 'audit_log'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        username = db.Column(db.String(80))
        action = db.Column(db.String(50))
        patient_id = db.Column(db.String(50))
        timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    class RecentlyViewedPatient(db.Model):
        __tablename__ = 'recently_viewed_patient'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        patient_id = db.Column(db.String(50))
        ward_num = db.Column(db.String(50))
        patient_name = db.Column(db.String(100))
        viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

        def to_dict(self):
            return {
                'patient_id': self.patient_id,
                'ward_num': self.ward_num,
                'patient_name': self.patient_name,
                'viewed_at': self.viewed_at.strftime('%Y-%m-%d %H:%M:%S')
            }

    class CareNote(db.Model):
        __tablename__ = 'care_note'
        id = db.Column(db.Integer, primary_key=True)
        patient_id = db.Column(db.String(50))
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        ward_id = db.Column(db.String(50))
        patient_name = db.Column(db.String(100))
        note = db.Column(db.Text, nullable=False)
        staff = db.Column(db.String(100))
        timestamp = db.Column(db.DateTime, default=datetime.utcnow)
        is_pdf_note = db.Column(db.Boolean, default=False)

        def to_dict(self):
            return {
                'id': self.id,
                'patient_id': self.patient_id,
                'user_id': self.user_id,
                'ward_id': self.ward_id,
                'note': self.note,
                'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }

    class Settings(db.Model):
        __tablename__ = 'settings'
        id = db.Column(db.Integer, primary_key=True)
        key = db.Column(db.String(50), unique=True, nullable=False)
        value = db.Column(db.String(255))

        @staticmethod
        def get_setting(key, default=None):
            # Handle case where db might not be initialized yet
            if db is None or not hasattr(Settings, 'query'):
                return default
                
            setting = Settings.query.filter_by(key=key).first()
            return setting.value if setting else default

        @staticmethod
        def set_setting(key, value):
            setting = Settings.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = Settings(key=key, value=value)
                db.session.add(setting)
            db.session.commit()

    # Update module globals after defining the classes 
    globals()['User'] = User
    globals()['Ward'] = Ward
    globals()['Patient'] = Patient
    globals()['AuditLog'] = AuditLog
    globals()['RecentlyViewedPatient'] = RecentlyViewedPatient
    globals()['CareNote'] = CareNote
    globals()['Settings'] = Settings
    
    return User, Ward, Patient, AuditLog, RecentlyViewedPatient, CareNote, Settings

def register_models():
    """No longer needed since we handle this in init_db"""
    pass  # This is now a no-op for backward compatibility
