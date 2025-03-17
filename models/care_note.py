from . import db
from datetime import datetime

class CareNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ward_id = db.Column(db.String(50), nullable=True)
    patient_name = db.Column(db.String(100), nullable=True)  # Add patient name column

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'note': self.note,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id,
            'ward_id': self.ward_id,
            'patient_name': self.patient_name
        }
