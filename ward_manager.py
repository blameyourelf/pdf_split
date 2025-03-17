import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from pdf_processor import process_ward_pdf
from google_drive import GoogleDriveManager

# Class to manage ward data
class WardManager:
    """Manager for ward data and metadata."""
    
    def __init__(self):
        """Initialize the ward manager."""
        self.wards_data = {}
        self.is_loading_data = False
        self.pdf_directory = os.environ.get('PDF_DIRECTORY', os.path.join(os.getcwd(), 'pdfs'))
    
    def get_ward_metadata(self, drive_client=None):
        """
        Get ward metadata from Google Drive or local files.
        
        Args:
            drive_client: Optional Google Drive client
            
        Returns:
            Dictionary of ward metadata
        """
        # Try to load metadata from Google Drive
        folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
        if drive_client and folder_id:
            drive_metadata = drive_client.get_ward_metadata(folder_id)
            if drive_metadata:
                print("Using ward metadata from Google Drive")
                return drive_metadata
        
        # Fallback to local files
        print("Falling back to local PDF files")
        import re
        wards_meta = {}
        try:
            if not os.path.exists(self.pdf_directory):
                print(f"Warning: PDF directory {self.pdf_directory} does not exist")
                return {}
                
            ward_files = [f for f in os.listdir(self.pdf_directory) 
                         if f.startswith('ward_') and f.endswith('_records.pdf')]
            print(f"Found {len(ward_files)} ward PDF files locally")
            
            for pdf_filename in ward_files:
                # Extract ward name/number between 'ward_' and '_records.pdf'
                ward_part = pdf_filename[5:-12]  # Remove 'ward_' and '_records.pdf'
                
                # Determine display name
                if ward_part.startswith('Long_'):
                    display_name = f"Long {ward_part[5:]}"  # Convert Long_1 to "Long 1"
                elif ward_part.isdigit():
                    display_name = f"Ward {ward_part}"
                else:
                    display_name = ward_part
                
                # Store metadata
                full_path = os.path.join(self.pdf_directory, pdf_filename)
                wards_meta[ward_part] = {
                    "filename": full_path,
                    "display_name": display_name
                }
                print(f"Added local ward PDF: {ward_part} - {display_name}")
                
            return wards_meta
        except Exception as e:
            print(f"Error in get_ward_metadata: {str(e)}")
            return {}

    def load_specific_ward(self, ward_num):
        """
        Load a specific ward's data.
        
        Args:
            ward_num: Ward identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        print(f"Loading specific ward: {ward_num}")
        
        # Make sure we're working with a valid ward
        if ward_num not in self.wards_data:
            print(f"Ward {ward_num} not found in ward data")
            return False
            
        ward_info = self.wards_data[ward_num]
        print(f"Found ward in wards_data: {ward_num}")
        
        # Skip if patients already loaded
        if ward_info.get("patients") and len(ward_info["patients"]) > 0:
            print(f"Ward {ward_num} already has {len(ward_info['patients'])} patients loaded")
            return True
        
        # Clear cache to ensure fresh data
        process_ward_pdf.cache_clear()
        
        # Handle files based on their source (Google Drive vs Local)
        try:
            if "file_id" in ward_info:
                # Google Drive file
                file_id = ward_info["file_id"]
                filename = ward_info["filename"]
                print(f"Loading Google Drive file: {filename} (ID: {file_id})")
                
                from app import get_drive_client
                # Get local file path
                local_path = get_drive_client().get_local_path(file_id, filename)
                if local_path and os.path.exists(local_path):
                    print(f"Processing PDF from local path: {local_path}")
                    patient_data = process_ward_pdf(local_path)
                    if not patient_data:
                        print(f"No patients found in {local_path}")
                        patient_data = {}
                    else:
                        print(f"Found {len(patient_data)} patients in {local_path}")
                else:
                    print(f"Failed to get local path for file {filename}")
                    patient_data = {}
            else:
                # Local file
                pdf_filename = ward_info["filename"]
                print(f"Loading local file: {pdf_filename}")
                
                if os.path.exists(pdf_filename):
                    patient_data = process_ward_pdf(pdf_filename)
                    if not patient_data:
                        print(f"No patients found in {pdf_filename}")
                        patient_data = {}
                    else:
                        print(f"Found {len(patient_data)} patients in {pdf_filename}")
                else:
                    print(f"File {pdf_filename} does not exist")
                    patient_data = {}
            
            # Update ward data with patients
            self.wards_data[ward_num]["patients"] = patient_data
            
            return True
            
        except Exception as e:
            print(f"Error loading ward {ward_num}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def load_ward_patients(self, ward_num):
        """
        Load patient data for a specific ward.
        
        Args:
            ward_num: Ward identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        if ward_num not in self.wards_data:
            print(f"Ward {ward_num} not found in ward data")
            return False
            
        # Skip if already loaded
        if self.wards_data[ward_num].get("patients") and len(self.wards_data[ward_num]["patients"]) > 0:
            print(f"Ward {ward_num} already has {len(self.wards_data[ward_num]['patients'])} patients loaded")
            return True
        
        # Use load_specific_ward to load data
        return self.load_specific_ward(ward_num)
    
    def load_ward_data_background(self, drive_client=None):
        """
        Load ward metadata in a background thread.
        
        Args:
            drive_client: Optional Google Drive client
        """
        # Load ward metadata (either from Drive or locally)
        metadata = self.get_ward_metadata(drive_client)
        if metadata:
            # Explicitly update the global variable with retrieved data
            self.wards_data.clear()
            self.wards_data.update(metadata)
            print(f"Loaded metadata for {len(self.wards_data)} wards")
        else:
            print("Warning: Failed to load any ward metadata")
        self.is_loading_data = False
    
    def init_ward_data(self, drive_client=None):
        """
        Initialize ward data loading in the background.
        
        Args:
            drive_client: Optional Google Drive client
        """
        self.is_loading_data = True
        threading.Thread(target=self.load_ward_data_background, args=(drive_client,)).start()
    
    def get_patient_info_from_ward_data(self, patient_id, ward_id=None):
        """
        Get patient information from ward data.
        
        Args:
            patient_id: Patient identifier
            ward_id: Optional ward identifier to search in
            
        Returns:
            Tuple of (patient_name, ward_display_name, ward_id)
        """
        # First try the specific ward if provided
        if ward_id and ward_id in self.wards_data:
            if not self.wards_data[ward_id].get("patients"):
                self.load_ward_patients(ward_id)
                
            ward_info = self.wards_data[ward_id]
            patients = ward_info.get("patients", {})
            if patient_id in patients:
                return (
                    patients[patient_id].get("name", "Unknown"),
                    ward_info.get("display_name", ward_id),
                    ward_id
                )
        
        # Build a list of wards to check first (frequently used wards)
        from app import db, RecentlyViewedPatient
        from flask_login import current_user
        
        frequently_used_wards = []
        try:
            # Get wards from recently viewed patients
            recent_views = RecentlyViewedPatient.query.filter_by(
                user_id=current_user.id
            ).distinct(RecentlyViewedPatient.ward_num).all()
            
            for rv in recent_views:
                if rv.ward_num and rv.ward_num not in frequently_used_wards:
                    frequently_used_wards.append(rv.ward_num)
                    
            # Check frequent wards first
            for ward_num in frequently_used_wards:
                if ward_num in self.wards_data:
                    if not self.wards_data[ward_num].get("patients"):
                        self.load_ward_patients(ward_num)
                    ward_info = self.wards_data[ward_num]
                    patients = ward_info.get("patients", {})
                    if patient_id in patients:
                        return (
                            patients[patient_id].get("name", "Unknown"),
                            ward_info.get("display_name", ward_num),
                            ward_num
                        )
            
            # If not found in frequent wards, check remaining wards as needed
            for ward_num, ward_info in self.wards_data.items():
                if ward_num in frequently_used_wards:
                    continue  # Skip already checked wards
                if not ward_info.get("patients"):
                    self.load_ward_patients(ward_num)
                patients = ward_info.get("patients", {})
                if patient_id in patients:
                    return (
                        patients[patient_id].get("name", "Unknown"),
                        ward_info.get("display_name", ward_num),
                        ward_num
                    )
        except Exception as e:
            print(f"Error in get_patient_info_from_ward_data: {str(e)}")
        
        # Not found in any ward
        return ("Unknown", "Unknown", None)

# Create a global instance
ward_manager = WardManager()
