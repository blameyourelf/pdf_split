from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')
    default_ward = db.Column(db.String(50), nullable=True)

class AuditLog(db.Model):
    __table_args__ = {'extend_existing': True}
    __bind_key__ = 'audit'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    patient_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Patient(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(50))
    current_ward = db.Column(db.String(50))
    pdf_file = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Note(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    staff_name = db.Column(db.String(100), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    ward_id = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, nullable=False)
    is_pdf_note = db.Column(db.Boolean, default=False)
    system_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    patient = db.relationship('Patient', backref=db.backref('notes', lazy=True))
    system_user = db.relationship('User', backref=db.backref('notes', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'staff_name': self.staff_name,
            'note_text': self.note_text,
            'ward_id': self.ward_id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_pdf_note': self.is_pdf_note,
            'system_user_id': self.system_user_id
        }

class Ward(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    ward_number = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100))
    pdf_file = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Settings(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get_setting(key, default='false'):
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

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value
        }

# Add these functions to get settings
def get_notes_enabled():
    """Check if notes adding is enabled in the settings"""
    enabled_setting = Settings.get_setting('notes_enabled', 'true')
    return enabled_setting.lower() == 'true'

def get_timeout_enabled():
    """Check if session timeout is enabled in the settings"""
    enabled_setting = Settings.get_setting('timeout_enabled', 'false')
    return enabled_setting.lower() == 'true'

def get_timeout_minutes():
    """Get the timeout minutes from settings, with a default of 30"""
    minutes_setting = Settings.get_setting('timeout_minutes', '30')
    try:
        return int(minutes_setting)
    except ValueError:
        return 30  # Default if the setting isn't a valid number

class CareNote(db.Model):
    """Model for care notes added to patients during downtime"""
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)  # External patient ID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)  # Actual note content
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ward_id = db.Column(db.String(50))  # Ward where the note was added
    patient_name = db.Column(db.String(100))  # Store patient name for efficiency
    
    user = db.relationship('User', backref=db.backref('care_notes', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'user_id': self.user_id,
            'note': self.note,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'ward_id': self.ward_id,
            'patient_name': self.patient_name
        }

class RecentlyViewedPatient(db.Model):
    """Model to track recently viewed patients for each user"""
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.String(50), nullable=False)  # External patient ID
    ward_num = db.Column(db.String(50))  # Ward where the patient is located
    patient_name = db.Column(db.String(100))  # Store patient name
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('recent_patients', lazy=True))
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'patient_id': self.patient_id,
            'ward_num': self.ward_num,
            'patient_name': self.patient_name,
            'viewed_at': self.viewed_at.strftime('%Y-%m-%d %H:%M:%S')
        }
