import os
import re
import fitz  # PyMuPDF
from functools import lru_cache
from typing import Dict, Any
import traceback

@lru_cache(maxsize=32)
def process_ward_pdf(pdf_path):
    """Process a ward PDF and extract patient data with robust error handling."""
    print(f"Processing PDF: {pdf_path}")
    patient_data = {}
    
    try:
        # Handle Google Drive file info dictionary
        if isinstance(pdf_path, dict):
            from app import drive_manager
            if 'file_id' in pdf_path:
                local_path = drive_manager.get_local_path(pdf_path['file_id'], pdf_path['filename'])
                if not local_path:
                    print(f"Failed to download file from Google Drive: {pdf_path['filename']}")
                    return {}
                pdf_path = local_path
                print(f"Using local path: {pdf_path}")
            else:
                print("Invalid file info dictionary")
                return {}
        
        # Verify file exists
        if not os.path.exists(pdf_path):
            print(f"File not found: {pdf_path}")
            return {}
            
        # Check file size
        file_size = os.path.getsize(pdf_path)
        print(f"PDF file size: {file_size} bytes")
        if file_size == 0:
            print("PDF file is empty")
            return {}
            
        # Try to open PDF
        try:
            pdf = fitz.open(pdf_path)
            page_count = len(pdf)
            print(f"PDF opened successfully with {page_count} pages")
        except Exception as e:
            print(f"Failed to open PDF: {str(e)}")
            return {}
            
        # Get bookmarks/table of contents
        try:
            toc = pdf.get_toc()
            print(f"Found {len(toc)} bookmarks")
            
            if len(toc) == 0:
                # Try to extract patients without bookmarks
                print("No bookmarks found, trying to extract patient data from content")
                # This is where you could add alternative extraction logic
                return {}
                
            # Process bookmarks to extract patient data
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
                            
                            patient_data[patient_id] = {
                                "name": name,
                                "page": page - 1  # Convert to 0-indexed
                            }
                            print(f"Extracted patient: {name} ({patient_id})")
                    except Exception as e:
                        print(f"Error processing bookmark '{title}': {str(e)}")
                        continue
                        
            pdf.close()
            print(f"Extracted {len(patient_data)} patients from PDF")
            return patient_data
            
        except Exception as e:
            print(f"Error extracting bookmarks: {str(e)}")
            return {}
            
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        traceback.print_exc()
        return {}
