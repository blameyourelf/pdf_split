from . import db
from datetime import datetime

class RecentlyViewedPatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.String(50), nullable=False)
    ward_num = db.Column(db.String(50), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'patient_id': self.patient_id,
            'ward_num': self.ward_num,
            'patient_name': self.patient_name,
            'viewed_at': self.viewed_at.strftime('%Y-%m-%d %H:%M:%S')
        }
