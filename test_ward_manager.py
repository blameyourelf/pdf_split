"""
Integration tests for the ward_manager module.
"""

import os
import unittest
import tempfile
import shutil
from ward_manager import WardManager

class MockDriveClient:
    """Mock implementation of SimpleDriveClient for testing."""
    
    def __init__(self, ward_files=None):
        self.ward_files = ward_files or {}
    
    def get_ward_metadata(self, folder_id):
        """Return mock ward metadata."""
        return self.ward_files
    
    def get_local_path(self, file_id, filename):
        """Mock getting a local path for a file."""
        return os.path.join(tempfile.gettempdir(), filename)

class TestWardManager(unittest.TestCase):
    """Test suite for WardManager."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for PDF files
        self.test_dir = tempfile.mkdtemp()
        
        # Create a WardManager instance with the test directory
        self.ward_manager = WardManager()
        self.ward_manager.pdf_directory = self.test_dir
        
        # Create some mock PDF files
        for ward_num in ['1', '2', 'ICU', 'CCU']:
            filename = f"ward_{ward_num}_records.pdf"
            filepath = os.path.join(self.test_dir, filename)
            with open(filepath, 'w') as f:
                f.write(f"Mock PDF for Ward {ward_num}")
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_get_ward_metadata_local(self):
        """Test getting ward metadata from local files."""
        # Get ward metadata
        metadata = self.ward_manager.get_ward_metadata()
        
        # Check that the expected wards are found
        self.assertIn('1', metadata)
        self.assertIn('2', metadata)
        self.assertIn('ICU', metadata)
        self.assertIn('CCU', metadata)
        
        # Check that display names are correct
        self.assertEqual(metadata['1']['display_name'], 'Ward 1')
        self.assertEqual(metadata['2']['display_name'], 'Ward 2')
        self.assertEqual(metadata['ICU']['display_name'], 'ICU')
        self.assertEqual(metadata['CCU']['display_name'], 'CCU')
        
        # Check that filenames are correct
        self.assertTrue(metadata['1']['filename'].endswith('ward_1_records.pdf'))
        self.assertTrue(metadata['ICU']['filename'].endswith('ward_ICU_records.pdf'))
    
    def test_get_ward_metadata_drive(self):
        """Test getting ward metadata from Google Drive."""
        # Create a mock drive client with some ward files
        mock_drive_files = {
            '3': {
                'file_id': 'mock_file_id_3',
                'filename': 'ward_3_records.pdf',
                'display_name': 'Ward 3'
            },
            'ED': {
                'file_id': 'mock_file_id_ed',
                'filename': 'ward_ED_records.pdf',
                'display_name': 'ED'
            }
        }
        mock_client = MockDriveClient(mock_drive_files)
        
        # Get ward metadata
        metadata = self.ward_manager.get_ward_metadata(mock_client)
        
        # Check that the expected wards are found
        self.assertIn('3', metadata)
        self.assertIn('ED', metadata)
        
        # Check that file IDs are preserved
        self.assertEqual(metadata['3']['file_id'], 'mock_file_id_3')
        self.assertEqual(metadata['ED']['file_id'], 'mock_file_id_ed')
    
    def test_init_ward_data(self):
        """Test initializing ward data."""
        # Create a mock drive client with some ward files
        mock_drive_files = {
            '3': {
                'file_id': 'mock_file_id_3',
                'filename': 'ward_3_records.pdf',
                'display_name': 'Ward 3'
            }
        }
        mock_client = MockDriveClient(mock_drive_files)
        
        # Initialize ward data
        self.ward_manager.init_ward_data(mock_client)
        
        # Give the background thread a moment to complete
        import time
        time.sleep(0.5)
        
        # Check that ward data has been loaded
        self.assertFalse(self.ward_manager.is_loading_data)
        self.assertGreater(len(self.ward_manager.wards_data), 0)
    
    def test_get_patient_info_empty(self):
        """Test getting patient info when data is empty."""
        # Fill wards_data with empty ward info
        self.ward_manager.wards_data = {
            '1': {'display_name': 'Ward 1', 'patients': {}},
            '2': {'display_name': 'Ward 2', 'patients': {}}
        }
        
        # Try to get info for a non-existent patient
        name, ward_name, ward_id = self.ward_manager.get_patient_info_from_ward_data('non_existent')
        
        # Check default values are returned
        self.assertEqual(name, 'Unknown')
        self.assertEqual(ward_name, 'Unknown')
        self.assertIsNone(ward_id)
    
    def test_load_specific_ward_not_found(self):
        """Test loading a ward that doesn't exist."""
        # Try to load a non-existent ward
        result = self.ward_manager.load_specific_ward('non_existent')
        
        # Check that the operation fails
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
