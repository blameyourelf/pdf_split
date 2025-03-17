import json
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Ward(Base):
    """Ward model for storing ward information."""
    __tablename__ = 'wards'
    
    id = Column(String(50), primary_key=True)
    display_name = Column(String(100))
    filename = Column(String(255))
    file_id = Column(String(255), nullable=True)  # For Google Drive integration
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to patients
    patients = relationship('Patient', back_populates='ward')

class Patient(Base):
    """Patient model for storing patient information."""
    __tablename__ = 'patients'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    ward_id = Column(String(50), ForeignKey('wards.id'), nullable=False)
    additional_info = Column(Text, nullable=True)  # JSON field for additional info
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to ward
    ward = relationship('Ward', back_populates='patients')
    
    def get_info_dict(self):
        """Convert additional_info JSON to dictionary."""
        try:
            return json.loads(self.additional_info) if self.additional_info else {}
        except json.JSONDecodeError:
            return {}
