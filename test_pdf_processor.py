"""
Integration tests for the pdf_processor module.
"""

import os
import unittest
import tempfile
import shutil
from pdf_processor import extract_patient_info, process_ward_pdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

class TestPDFProcessor(unittest.TestCase):
    """Test suite for PDF processing functions."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test PDFs
        self.test_dir = tempfile.mkdtemp()
        
        # Create test PDF with simple patient data
        self.create_test_pdfs()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory and all test files
        shutil.rmtree(self.test_dir)
    
    def create_test_pdfs(self):
        """Create test PDF files for testing."""
        # Create a simple test PDF with patient information
        self.test_pdf_path = os.path.join(self.test_dir, "test_ward.pdf")
        self.create_simple_patient_pdf(self.test_pdf_path)
        
        # Create a bookmarked PDF
        self.bookmarked_pdf_path = os.path.join(self.test_dir, "bookmarked_ward.pdf")
        self.create_bookmarked_pdf(self.bookmarked_pdf_path)
    
    def create_simple_patient_pdf(self, filepath):
        """Create a simple PDF with patient information."""
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        # Patient 1
        c.drawString(100, height - 100, "Patient Record - Ward 1")
        c.drawString(100, height - 130, "Patient ID: 12345")
        c.drawString(100, height - 150, "Name: John Smith")
        c.drawString(100, height - 170, "Ward: 1")
        c.drawString(100, height - 190, "DOB: 1980-01-15")
        
        # Care notes section
        c.drawString(100, height - 230, "Continuous Care Notes")
        c.drawString(100, height - 250, "Date & Time    Staff Member    Notes")
        c.drawString(100, height - 270, "2023-01-01 08:00    Dr. Jones    Initial assessment")
        
        # Patient 2 on next page
        c.showPage()
        c.drawString(100, height - 100, "Patient Record - Ward 1")
        c.drawString(100, height - 130, "Patient ID: 67890")
        c.drawString(100, height - 150, "Name: Jane Doe")
        c.drawString(100, height - 170, "Ward: 1")
        c.drawString(100, height - 190, "DOB: 1975-05-20")
        
        c.drawString(100, height - 230, "Continuous Care Notes")
        c.drawString(100, height - 250, "Date & Time    Staff Member    Notes")
        c.drawString(100, height - 270, "2023-01-01 09:00    Dr. Smith    Medication administered")
        
        c.save()
    
    def create_bookmarked_pdf(self, filepath):
        """Create a PDF with bookmarks for patients."""
        from fitz import Document
        
        # Create a blank document
        doc = Document()
        
        # Add pages for patients
        for i in range(2):
            # Add a page
            page = doc.new_page()
            
            # Add some text
            patient_id = f"{10001 + i}"
            name = f"Patient {i+1}"
            
            text = f"Patient Record - Ward 1\n"
            text += f"Patient ID: {patient_id}\n"
            text += f"Name: {name}\n"
            text += f"Ward: 1\n"
            text += f"DOB: 1980-01-{15+i}\n\n"
            text += "Continuous Care Notes\n"
            text += "Date & Time    Staff Member    Notes\n"
            text += f"2023-01-01 {8+i}:00    Dr. Jones    Initial assessment"
            
            page.insert_text((100, 100), text)
            
            # Add bookmark for this page
            doc.set_toc([
                [1, f"Patient: {name} ({patient_id})", i+1]
            ])
        
        # Save the document
        doc.save(filepath)
    
    def test_extract_patient_info(self):
        """Test extracting patient info from a PDF."""
        # Extract patient data
        patient_data = extract_patient_info(self.test_pdf_path)
        
        # Check that the expected patients are found
        self.assertIn('12345', patient_data)
        self.assertIn('67890', patient_data)
        
        # Check patient 1 details
        patient1 = patient_data['12345']
        self.assertEqual(patient1['name'], 'John Smith')
        self.assertIn('DOB', patient1['info'])
        self.assertEqual(patient1['info']['DOB'], '1980-01-15')
        
        # Check patient 2 details
        patient2 = patient_data['67890']
        self.assertEqual(patient2['name'], 'Jane Doe')
        self.assertIn('DOB', patient2['info'])
        self.assertEqual(patient2['info']['DOB'], '1975-05-20')
        
        # Check that care notes were extracted
        self.assertTrue(len(patient1['care_notes']) > 0)
        self.assertTrue(len(patient2['care_notes']) > 0)
    
    def test_extract_specific_patient(self):
        """Test extracting a specific patient by ID."""
        # Extract specific patient
        patient_data = extract_patient_info(self.test_pdf_path, patient_id='12345')
        
        # Check that only the requested patient is returned
        self.assertEqual(len(patient_data), 1)
        self.assertIn('12345', patient_data)
        self.assertNotIn('67890', patient_data)
    
    def test_process_ward_pdf(self):
        """Test the process_ward_pdf function."""
        # Process the test PDF
        patient_data = process_ward_pdf(self.test_pdf_path)
        
        # Check that patients were found
        self.assertGreater(len(patient_data), 0)
        self.assertIn('12345', patient_data)
        
        # Clear the cache to ensure we get fresh data
        process_ward_pdf.cache_clear()
        
        # Test with non-existent file
        bad_data = process_ward_pdf("/non/existent/path.pdf")
        self.assertEqual(len(bad_data), 0)

if __name__ == '__main__':
    unittest.main()
