import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("database_operations.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create base class for declarative models
Base = declarative_base()

class Ward(Base):
    __tablename__ = 'wards'
    
    id = Column(String, primary_key=True)  # Ward identifier (e.g., "1", "CCU", "ICU")
    display_name = Column(String, nullable=False)  # Display name (e.g., "Ward 1", "CCU")
    filename = Column(String)  # Original PDF filename
    file_id = Column(String)  # Google Drive file ID if applicable
    last_updated = Column(DateTime, default=datetime.now)
    
    # Relationship to patients in this ward
    patients = relationship("Patient", back_populates="ward", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Ward(id='{self.id}', display_name='{self.display_name}')>"

class Patient(Base):
    __tablename__ = 'patients'
    
    id = Column(String, primary_key=True)  # Patient ID
    name = Column(String, nullable=False)  # Patient name
    ward_id = Column(String, ForeignKey('wards.id'), nullable=False)
    dob = Column(String)  # Date of birth
    age = Column(Integer)
    gender = Column(String)
    pdf_page = Column(Integer)  # Page number in the original PDF
    vitals = Column(Text)  # Store vitals as text if present
    additional_info = Column(Text)  # JSON field for flexible additional info
    
    # Relationships
    ward = relationship("Ward", back_populates="patients")
    care_notes = relationship("CareNote", back_populates="patient", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Patient(id='{self.id}', name='{self.name}', ward='{self.ward_id}')>"

class CareNote(Base):
    __tablename__ = 'care_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String, ForeignKey('patients.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    staff = Column(String)  # Staff member who wrote the note
    note = Column(Text, nullable=False)
    is_pdf_note = Column(Boolean, default=False)  # Whether note is from PDF or added later
    
    # Relationship
    patient = relationship("Patient", back_populates="care_notes")
    
    def __repr__(self):
        return f"<CareNote(patient_id='{self.patient_id}', timestamp='{self.timestamp}')>"

def init_db(db_path):
    """Initialize the database at the given path."""
    try:
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        logger.info(f"Initializing database at {db_path}")
        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        
        # Create a session factory
        Session = sessionmaker(bind=engine)
        
        logger.info("Database initialized successfully")
        return engine, Session
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    # Example: Create the database schema
    db_path = os.path.join("instance", "patient_data.db")
    engine, Session = init_db(db_path)
    logger.info(f"Database created at {db_path}")
