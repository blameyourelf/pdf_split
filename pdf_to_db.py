import os
import re
import json
import fitz  # PyMuPDF
import logging
import traceback
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
import tempfile

# Import our modules
from database_schema import Ward, Patient, CareNote
from db_manager import db_manager
from simple_drive import SimpleDriveClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pdf_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFExtractor:
    """Extract patient data from PDFs and store it in the database."""
    
    def __init__(self):
        """Initialize the PDF extractor."""
        self.drive_client = SimpleDriveClient()
    
    def extract_patient_data_from_file(self, pdf_path: str, ward_id: str, 
                                       ward_display_name: str, 
                                       file_id: Optional[str] = None) -> bool:
        """
        Extract patient data from a PDF file and store it in the database.
        
        Args:
            pdf_path: Path to the PDF file
            ward_id: Ward identifier
            ward_display_name: Display name for the ward
            file_id: Google Drive file ID (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Processing PDF: {pdf_path} for ward {ward_id}")
            
            # Check if file exists
            if not os.path.exists(pdf_path):
                logger.error(f"File not found: {pdf_path}")
                return False
                
            # Check file size
            file_size = os.path.getsize(pdf_path)
            logger.info(f"PDF file size: {file_size} bytes")
            if file_size == 0:
                logger.error("PDF file is empty")
                return False
            
            with db_manager.session_scope() as session:
                # Create or update ward record
                ward = session.query(Ward).filter_by(id=ward_id).first()
                if not ward:
                    ward = Ward(
                        id=ward_id,
                        display_name=ward_display_name,
                        filename=os.path.basename(pdf_path),
                        file_id=file_id,
                        last_updated=datetime.now()
                    )
                    session.add(ward)
                else:
                    ward.display_name = ward_display_name
                    ward.filename = os.path.basename(pdf_path)
                    ward.file_id = file_id
                    ward.last_updated = datetime.now()
                
                # First try to extract via bookmarks (more reliable structure)
                patient_data = self.extract_from_bookmarks(pdf_path)
                
                # If no patients found via bookmarks, try text extraction
                if not patient_data:
                    logger.info(f"No bookmarks found, attempting text extraction")
                    patient_data = self.extract_from_text(pdf_path)
                    
                if not patient_data:
                    logger.warning(f"No patient data found in {pdf_path}")
                    return False
                    
                logger.info(f"Found {len(patient_data)} patients in {pdf_path}")
                
                # Process each patient and add to database
                for patient_id, data in patient_data.items():
                    try:
                        self._add_patient_to_db(session, patient_id, data, ward_id)
                    except Exception as e:
                        logger.error(f"Error adding patient {patient_id} to database: {str(e)}")
                        traceback.print_exc()
                
                logger.info(f"Successfully processed ward {ward_id} with {len(patient_data)} patients")
                return True
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            traceback.print_exc()
            return False
    
    def extract_from_bookmarks(self, pdf_path: str) -> Dict[str, Any]:
        """Extract patient data from PDF bookmarks."""
        patient_data = {}
        try:
            with fitz.open(pdf_path) as pdf:
                toc = pdf.get_toc()
                logger.info(f"Found {len(toc)} bookmarks")
                
                if len(toc) == 0:
                    return {}
                    
                # Process bookmarks
                for item in toc:
                    level, title, page = item
                    if level == 0:  # Top-level bookmarks only
                        try:
                            # Extract patient ID from title (e.g., "Patient: John Smith (12345678)")
                            id_match = re.search(r'\((\d+)\)', title)
                            if id_match:
                                patient_id = id_match.group(1)
                                # Extract name from title
                                name_match = re.match(r'Patient:\s+(.*?)\s+\(', title)
                                name = name_match.group(1) if name_match else "Unknown"
                                
                                # Extract text from the patient's page
                                text_content = ""
                                if 0 <= page-1 < len(pdf):
                                    text_content = pdf[page-1].get_text()
                                
                                # Extract structured data
                                info_dict = self._extract_patient_info(text_content)
                                vitals = self._extract_vitals(text_content)
                                
                                # Store patient data
                                patient_data[patient_id] = {
                                    "name": name,
                                    "page": page - 1,  # Convert to 0-indexed
                                    "info": info_dict,
                                    "vitals": vitals,
                                    "care_notes": self._extract_care_notes(text_content)
                                }
                                
                                logger.info(f"Extracted patient: {name} ({patient_id})")
                        except Exception as e:
                            logger.error(f"Error processing bookmark '{title}': {str(e)}")
                
                return patient_data
                
        except Exception as e:
            logger.error(f"Error extracting bookmarks from {pdf_path}: {str(e)}")
            return {}
            
    def extract_from_text(self, pdf_path: str) -> Dict[str, Any]:
        """Extract patient data by scanning page text if no bookmarks exist."""
        patient_data = {}
        try:
            with fitz.open(pdf_path) as pdf:
                current_patient_id = None
                current_patient_data = {}
                
                for page_number in range(len(pdf)):
                    text = pdf[page_number].get_text()
                    if not text:
                        continue
                        
                    # Look for patient headers
                    # Pattern: "Patient Record - Ward X" followed by patient info
                    if "Patient Record - Ward" in text:
                        # Process previous patient if any
                        if current_patient_id and current_patient_data:
                            patient_data[current_patient_id] = current_patient_data
                        
                        # Look for patient ID and name
                        id_match = re.search(r'Patient ID:\s*(\d+)', text)
                        name_match = re.search(r'Name:\s*([\w\s]+)', text)
                        
                        if id_match:
                            current_patient_id = id_match.group(1).strip()
                            name = name_match.group(1).strip() if name_match else "Unknown"
                            
                            # Extract structured data
                            info_dict = self._extract_patient_info(text)
                            vitals = self._extract_vitals(text)
                            
                            # Initialize new patient data
                            current_patient_data = {
                                "name": name,
                                "page": page_number,
                                "info": info_dict,
                                "vitals": vitals,
                                "care_notes": self._extract_care_notes(text)
                            }
                            
                            logger.info(f"Text extraction found patient: {name} ({current_patient_id}) on page {page_number}")
                    
                    # If we're in a patient record, add more care notes if found
                    elif current_patient_id and "Continuous Care Notes" in text:
                        additional_notes = self._extract_care_notes(text)
                        current_patient_data["care_notes"].extend(additional_notes)
                
                # Add the last patient if any
                if current_patient_id and current_patient_data:
                    patient_data[current_patient_id] = current_patient_data
                
                return patient_data
                
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            traceback.print_exc()
            return {}
    
    def _extract_patient_info(self, text: str) -> Dict[str, str]:
        """Extract structured patient information from text."""
        info_dict = {}
        
        # Extract common fields
        patterns = {
            "Patient ID": r'Patient ID:\s*([\w\d]+)',
            "Name": r'Name:\s*([\w\s]+)',
            "Ward": r'Ward:\s*([\w\s]+)',
            "DOB": r'DOB:\s*([\d-]+)',
            "Gender": r'Gender:\s*(\w+)',
            "Age": r'Age:\s*(\d+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                info_dict[key] = match.group(1).strip()
                
        # Try to find any additional structured information
        lines = text.split('\n')
        in_info_section = False
        
        for line in lines:
            # Detect if we're in the patient info section (assumes patient info comes first)
            if "Patient Record" in line:
                in_info_section = True
                continue
                
            # Stop when we hit care notes or other sections
            if "Continuous Care Notes" in line:
                in_info_section = False
                break
                
            # If in info section, look for key-value pairs
            if in_info_section and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value and key not in info_dict:
                        info_dict[key] = value
                        
        return info_dict
    
    def _extract_care_notes(self, text: str) -> List[Dict[str, str]]:
        """Extract care notes from patient text."""
        notes = []
        
        # Check if care notes section exists
        if "Continuous Care Notes" not in text:
            return notes
            
        # Find the care notes section
        parts = text.split("Continuous Care Notes")
        if len(parts) < 2:
            return notes
            
        care_notes_text = parts[1]
        
        # Try to parse the table-like structure
        # Pattern: Date & Time | Staff Member | Notes
        lines = care_notes_text.split('\n')
        current_note = {}
        
        for line in lines:
            # Skip header line
            if "Date & Time" in line and "Staff Member" in line and "Notes" in line:
                continue
                
            # Try to identify date/time pattern at the start of a line
            date_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', line)
            
            # If we found a new date/time, it's a new note
            if date_match:
                # Save previous note if any
                if current_note and "date" in current_note and "note" in current_note:
                    notes.append(current_note)
                    
                # Start new note
                parts = line.split('  ')  # Assuming spaces separate columns
                
                # Initialize with default values
                current_note = {
                    "date": date_match.group(1),
                    "staff": "",
                    "note": ""
                }
                
                # Try to identify staff and note content
                if len(parts) >= 3:
                    # More sophisticated parsing - find the staff part
                    staff_match = re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+,\s*[A-Z]+\b', line)
                    if staff_match:
                        current_note["staff"] = staff_match.group(0)
                        
                        # Note is everything after the staff
                        note_parts = line.split(staff_match.group(0))
                        if len(note_parts) > 1:
                            current_note["note"] = note_parts[1].strip()
                    else:
                        # Fallback if staff doesn't match expected pattern
                        current_note["note"] = " ".join(parts[2:]).strip()
            
            # If not a new note, add to the current note
            elif current_note:
                current_note["note"] += " " + line.strip()
        
        # Add the last note if any
        if current_note and "date" in current_note and "note" in current_note:
            notes.append(current_note)
            
        return notes
    
    def _extract_vitals(self, text: str) -> str:
        """Extract vital signs information if available."""
        # Look for a vitals section
        vital_patterns = [
            r'Vital Signs[:\s]+(.*?)(?=Continuous Care Notes|\Z)',
            r'Current Vital Signs[:\s]+(.*?)(?=Continuous Care Notes|\Z)'
        ]
        
        for pattern in vital_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
                
        # No vitals found
        return ""
        
    def _add_patient_to_db(self, session, patient_id: str, data: Dict[str, Any], ward_id: str):
        """Add a patient and related data to the database."""
        # Check if patient already exists
        patient = session.query(Patient).filter_by(id=patient_id).first()
        
        if not patient:
            # Create new patient
            info_dict = data.get("info", {})
            
            # Extract age if available
            age = None
            if "Age" in info_dict:
                try:
                    age = int(info_dict["Age"])
                except ValueError:
                    pass
                    
            # Create patient object
            patient = Patient(
                id=patient_id,
                name=data.get("name", "Unknown"),
                ward_id=ward_id,
                dob=info_dict.get("DOB", ""),
                age=age,
                gender=info_dict.get("Gender", ""),
                pdf_page=data.get("page", 0),
                vitals=data.get("vitals", ""),
                additional_info=json.dumps(info_dict)
            )
            
            session.add(patient)
            session.flush()  # Generate ID without committing transaction
        else:
            # Update existing patient
            patient.name = data.get("name", patient.name)
            patient.ward_id = ward_id
            
            # Update info if available
            if data.get("info"):
                info_dict = data.get("info", {})
                
                if "DOB" in info_dict:
                    patient.dob = info_dict["DOB"]
                    
                if "Age" in info_dict:
                    try:
                        patient.age = int(info_dict["Age"])
                    except ValueError:
                        pass
                        
                if "Gender" in info_dict:
                    patient.gender = info_dict["Gender"]
                    
                patient.additional_info = json.dumps(info_dict)
                
            patient.pdf_page = data.get("page", patient.pdf_page)
            patient.vitals = data.get("vitals", patient.vitals)
        
        # Add care notes
        care_notes = data.get("care_notes", [])
        
        # Remove existing PDF notes for this patient
        session.query(CareNote).filter_by(
            patient_id=patient_id, is_pdf_note=True
        ).delete()
        
        # Add new care notes
        for note_data in care_notes:
            try:
                timestamp = datetime.strptime(note_data["date"], "%Y-%m-%d %H:%M")
            except ValueError:
                # Fallback if date format doesn't match
                timestamp = datetime.now()
                
            care_note = CareNote(
                patient_id=patient_id,
                timestamp=timestamp,
                staff=note_data.get("staff", ""),
                note=note_data.get("note", ""),
                is_pdf_note=True  # Mark as coming from PDF
            )
            
            session.add(care_note)

def process_google_drive_pdfs(folder_id: str = None):
    """
    Download and process PDFs from Google Drive.
    
    Args:
        folder_id: Google Drive folder ID (optional)
    """
    try:
        # Initialize PDF extractor
        extractor = PDFExtractor()
        
        # Initialize Google Drive client
        drive_client = SimpleDriveClient()
        
        # Use folder ID from environment if not provided
        if not folder_id:
            folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
            
        if not folder_id:
            logger.error("No Google Drive folder ID provided")
            return
            
        logger.info(f"Downloading PDFs from Google Drive folder: {folder_id}")
        
        try:
            # Get ward metadata
            wards_meta = drive_client.get_ward_metadata(folder_id)
            
            if not wards_meta:
                logger.error("No ward metadata found in Google Drive folder")
                return
                
            logger.info(f"Found {len(wards_meta)} wards in Google Drive folder")
            
            # Process each ward
            for ward_id, ward_info in wards_meta.items():
                file_id = ward_info.get("file_id")
                filename = ward_info.get("filename")
                display_name = ward_info.get("display_name", f"Ward {ward_id}")
                
                if not file_id or not filename:
                    logger.warning(f"Missing file information for ward {ward_id}")
                    continue
                    
                try:
                    # Download file
                    logger.info(f"Downloading {filename} (ID: {file_id})")
                    local_path = drive_client.get_local_path(file_id, filename)
                    
                    if not local_path or not os.path.exists(local_path):
                        logger.error(f"Failed to download {filename}")
                        continue
                        
                    # Process PDF
                    logger.info(f"Processing {filename} for ward {ward_id}")
                    extractor.extract_patient_data_from_file(
                        local_path, ward_id, display_name, file_id
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing ward {ward_id}: {str(e)}")
                    traceback.print_exc()
                    
        except Exception as e:
            logger.error(f"Error getting ward metadata: {str(e)}")
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Error processing Google Drive PDFs: {str(e)}")
        traceback.print_exc()

def process_local_pdfs(pdf_directory: str = None):
    """
    Process PDFs from a local directory.
    
    Args:
        pdf_directory: Directory containing PDF files (optional)
    """
    try:
        # Initialize PDF extractor
        extractor = PDFExtractor()
        
        # Use PDF_DIRECTORY from environment if not provided
        if not pdf_directory:
            pdf_directory = os.environ.get('PDF_DIRECTORY', 'pdfs')
            
        if not os.path.exists(pdf_directory):
            logger.error(f"PDF directory not found: {pdf_directory}")
            return
            
        logger.info(f"Processing PDFs from local directory: {pdf_directory}")
        
        # Find ward PDFs
        pdf_files = [f for f in os.listdir(pdf_directory) 
                    if f.startswith('ward_') and f.endswith('_records.pdf')]
                    
        if not pdf_files:
            logger.error(f"No ward PDF files found in {pdf_directory}")
            return
            
        logger.info(f"Found {len(pdf_files)} ward PDF files")
        
        # Process each PDF
        for pdf_filename in pdf_files:
            try:
                # Extract ward ID from filename (between 'ward_' and '_records.pdf')
                ward_part = pdf_filename[5:-12]  # Remove 'ward_' and '_records.pdf'
                
                # Determine display name
                if ward_part.startswith('Long_'):
                    display_name = f"Long {ward_part[5:]}"  # Convert Long_1 to "Long 1"
                elif ward_part.isdigit():
                    display_name = f"Ward {ward_part}"
                else:
                    display_name = ward_part  # Keep special ward names as is
                    
                pdf_path = os.path.join(pdf_directory, pdf_filename)
                
                # Process PDF
                logger.info(f"Processing {pdf_filename} for ward {ward_part}")
                extractor.extract_patient_data_from_file(
                    pdf_path, ward_part, display_name
                )
                
            except Exception as e:
                logger.error(f"Error processing {pdf_filename}: {str(e)}")
                traceback.print_exc()
                
    except Exception as e:
        logger.error(f"Error processing local PDFs: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process PDFs and store data in SQLite database')
    parser.add_argument('--pdf-directory', help='Directory containing PDF files')
    parser.add_argument('--google-drive', action='store_true', help='Process PDFs from Google Drive')
    parser.add_argument('--folder-id', help='Google Drive folder ID')
    
    args = parser.parse_args()
    
    # Process PDFs
    if args.google_drive:
        process_google_drive_pdfs(args.folder_id)
    else:
        process_local_pdfs(args.pdf_directory)
        
    logger.info("PDF processing completed")
