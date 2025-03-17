from . import db
from datetime import datetime

class AuditLog(db.Model):
    __bind_key__ = 'audit'  # This tells SQLAlchemy to use the audit database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)  # Store username directly for persistence
    action = db.Column(db.String(50), nullable=False)
    patient_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
