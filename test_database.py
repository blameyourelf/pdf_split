"""
Integration tests for database functionality.
This script tests the database models, queries, and overall functionality.
"""

import os
import unittest
import tempfile
from datetime import datetime, timedelta

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Import the models module to test
import models
from models import User, AuditLog, RecentlyViewedPatient, CareNote, Settings

class TestDatabaseFunctionality(unittest.TestCase):
    """Test suite for database functionality."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a test Flask application
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Use an in-memory SQLite database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.audit_fd, self.audit_path = tempfile.mkstemp()
        
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['SQLALCHEMY_BINDS'] = {
            'audit': f'sqlite:///{self.audit_path}'
        }
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database
        self.db = SQLAlchemy(self.app)
        models.init_db(self.db)
        
        with self.app.app_context():
            # Create all tables
            self.db.create_all()
            self.db.create_all(bind=['audit'])
            
            # Add test data
            self._create_test_data()
    
    def tearDown(self):
        """Clean up after each test."""
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()
            self.db.drop_all(bind=['audit'])
        
        os.close(self.db_fd)
        os.unlink(self.db_path)
        os.close(self.audit_fd)
        os.unlink(self.audit_path)
    
    def _create_test_data(self):
        """Create test data for the database."""
        # Create test users
        from werkzeug.security import generate_password_hash
        
        admin = User(
            username='admin_test',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        
        nurse = User(
            username='nurse_test',
            password_hash=generate_password_hash('nurse123'),
            role='user',
            default_ward='1'
        )
        
        self.db.session.add_all([admin, nurse])
        self.db.session.commit()
        
        # Create settings
        settings = [
            Settings(key='notes_enabled', value='true'),
            Settings(key='timeout_enabled', value='true'),
            Settings(key='timeout_minutes', value='30')
        ]
        self.db.session.add_all(settings)
        self.db.session.commit()
        
        # Set instance variables for test user IDs
        self.admin_id = admin.id
        self.nurse_id = nurse.id
    
    def test_user_creation(self):
        """Test user creation and retrieval."""
        with self.app.app_context():
            # Query users
            admin = User.query.filter_by(username='admin_test').first()
            nurse = User.query.filter_by(username='nurse_test').first()
            
            # Assert users exist
            self.assertIsNotNone(admin)
            self.assertIsNotNone(nurse)
            
            # Test properties
            self.assertEqual(admin.role, 'admin')
            self.assertEqual(nurse.role, 'user')
            self.assertEqual(nurse.default_ward, '1')
    
    def test_settings(self):
        """Test settings creation and retrieval."""
        with self.app.app_context():
            # Test get_setting method
            notes_enabled = Settings.get_setting('notes_enabled')
            timeout_enabled = Settings.get_setting('timeout_enabled')
            timeout_minutes = Settings.get_setting('timeout_minutes')
            
            self.assertEqual(notes_enabled, 'true')
            self.assertEqual(timeout_enabled, 'true')
            self.assertEqual(timeout_minutes, '30')
            
            # Test default value
            unknown_setting = Settings.get_setting('unknown_key', 'default_value')
            self.assertEqual(unknown_setting, 'default_value')
            
            # Test setting a value
            Settings.set_setting('new_key', 'new_value')
            new_value = Settings.get_setting('new_key')
            self.assertEqual(new_value, 'new_value')
            
            # Test updating a value
            Settings.set_setting('notes_enabled', 'false')
            updated_value = Settings.get_setting('notes_enabled')
            self.assertEqual(updated_value, 'false')
    
    def test_care_notes(self):
        """Test care notes creation and retrieval."""
        with self.app.app_context():
            # Create a care note
            note1 = CareNote(
                patient_id='12345',
                user_id=self.nurse_id,
                note='Test note content',
                ward_id='1',
                patient_name='Test Patient'
            )
            
            note2 = CareNote(
                patient_id='12345',
                user_id=self.admin_id,
                note='Follow-up note',
                ward_id='1',
                patient_name='Test Patient',
                timestamp=datetime.utcnow() + timedelta(hours=1)
            )
            
            self.db.session.add_all([note1, note2])
            self.db.session.commit()
            
            # Query notes
            notes = CareNote.query.filter_by(patient_id='12345').order_by(
                CareNote.timestamp.desc()
            ).all()
            
            # Assert notes exist and are ordered correctly (newest first)
            self.assertEqual(len(notes), 2)
            self.assertEqual(notes[0].note, 'Follow-up note')
            self.assertEqual(notes[1].note, 'Test note content')
            
            # Test to_dict method
            note_dict = notes[0].to_dict()
            self.assertEqual(note_dict['patient_id'], '12345')
            self.assertEqual(note_dict['note'], 'Follow-up note')
            self.assertEqual(note_dict['ward_id'], '1')
            self.assertEqual(note_dict['patient_name'], 'Test Patient')
    
    def test_recently_viewed_patients(self):
        """Test recently viewed patients creation and retrieval."""
        with self.app.app_context():
            # Create recently viewed patients
            for i in range(1, 12):  # Create 11 entries (more than the 10 limit)
                recent = RecentlyViewedPatient(
                    user_id=self.nurse_id,
                    patient_id=f'1000{i}',
                    ward_num='1',
                    patient_name=f'Patient {i}'
                )
                # Set timestamps to be ordered
                recent.viewed_at = datetime.utcnow() + timedelta(minutes=i)
                self.db.session.add(recent)
            
            self.db.session.commit()
            
            # Query recently viewed patients
            recents = RecentlyViewedPatient.query.filter_by(
                user_id=self.nurse_id
            ).order_by(RecentlyViewedPatient.viewed_at.desc()).all()
            
            # Assert count and order
            self.assertEqual(len(recents), 11)
            self.assertEqual(recents[0].patient_id, '10011')  # Most recent should be the last added
            
            # Test to_dict method
            recent_dict = recents[0].to_dict()
            self.assertEqual(recent_dict['patient_id'], '10011')
            self.assertEqual(recent_dict['ward_num'], '1')
            self.assertEqual(recent_dict['patient_name'], 'Patient 11')
    
    def test_audit_log(self):
        """Test audit log creation and retrieval."""
        with self.app.app_context():
            # Create audit logs
            log1 = AuditLog(
                user_id=self.nurse_id,
                username='nurse_test',
                action='view_patient',
                patient_id='12345'
            )
            
            log2 = AuditLog(
                user_id=self.nurse_id,
                username='nurse_test',
                action='add_note',
                patient_id='12345'
            )
            
            log3 = AuditLog(
                user_id=self.admin_id,
                username='admin_test',
                action='view_audit_log'
            )
            
            self.db.session.add_all([log1, log2, log3])
            self.db.session.commit()
            
            # Query audit logs
            logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
            
            # Assert logs exist
            self.assertEqual(len(logs), 3)
            
            # Check patient specific logs
            patient_logs = AuditLog.query.filter_by(patient_id='12345').all()
            self.assertEqual(len(patient_logs), 2)
            
            # Check user specific logs
            nurse_logs = AuditLog.query.filter_by(user_id=self.nurse_id).all()
            self.assertEqual(len(nurse_logs), 2)
            
            admin_logs = AuditLog.query.filter_by(user_id=self.admin_id).all()
            self.assertEqual(len(admin_logs), 1)

if __name__ == '__main__':
    unittest.main()
