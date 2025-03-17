import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from contextlib import contextmanager

# Import the database schema
from database_schema import Base

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

class DatabaseManager:
    """Database manager for handling SQLAlchemy session and engine."""
    
    def __init__(self, db_url=None):
        """Initialize database connection."""
        if db_url is None:
            db_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/patient_data.db')
        
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def create_all_tables(self):
        """Create all tables in the database."""
        from db_models import Base
        Base.metadata.create_all(self.engine)

# Create a global instance for convenient import
db_manager = DatabaseManager()

if __name__ == "__main__":
    # Test database connection
    try:
        with db_manager.session_scope() as session:
            # Simple query to test connection
            result = session.execute("SELECT 1").scalar()
            logger.info(f"Database connection successful: {result}")
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
