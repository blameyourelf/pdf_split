import os
import re
import fitz  # PyMuPDF
from functools import lru_cache
from typing import Dict, Any, List, Optional
import traceback
from PyPDF2 import PdfReader
from datetime import datetime

def extract_patients_from_text(pdf) -> Dict[str, Any]:
    """Extract patient data by scanning each page text if no bookmarks exist."""
    patient_data = {}
    for page_number in range(len(pdf)):
        text = pdf[page_number].get_text()
        # Look for patterns like "Patient: John Smith (12345678)"
        for match in re.finditer(r'Patient:\s+(.*?)\s+\((\d+)\)', text):
            name = match.group(1).strip()
            patient_id = match.group(2).strip()
            if patient_id not in patient_data:
                patient_data[patient_id] = {"name": name, "page": page_number}
                print(f"Alternative extraction found patient: {name} ({patient_id}) on page {page_number}")
    return patient_data

def extract_patient_info(pdf_path, patient_id=None):
    """
    Extract patient info and notes while supporting multiple note formats.
    
    Args:
        pdf_path: Path to the PDF file
        patient_id: Optional patient ID to extract specific patient
        
    Returns:
        Dictionary of patient data keyed by patient ID
    """
    patient_data = {}
    current_patient = None
    current_patient_id = None
    try:
        reader = PdfReader(pdf_path)
        for page_idx in range(len(reader.pages)):
            page = reader.pages[page_idx]
            text = page.extract_text()
            # Check if this is a new patient record
            if "Patient Record - Ward" in text:
                # Save previous patient if exists
                if current_patient_id and current_patient:
                    if not patient_id or current_patient_id == patient_id:
                        patient_data[current_patient_id] = current_patient
                # Reset for new patient
                current_patient = {
                    "info": {},
                    "name": "Unknown",
                    "vitals": "",
                    "care_notes": []
                }
                current_patient_id = None
                in_care_notes = False
            
            # Extract patient ID - MUST do this for all patients
            if current_patient and not current_patient_id:
                id_match = re.search(r"Patient ID:\s*(\d+)", text)
                if id_match:
                    current_patient_id = id_match.group(1).strip()
                    
            # If we found the specific patient we're looking for, or we want all patients
            if not patient_id or (current_patient_id and (current_patient_id == patient_id)):
                # Extract name if we haven't yet
                if current_patient and current_patient["name"] == "Unknown":
                    name_match = re.search(r"Name:\s*([^\n]+)", text)
                    if name_match:
                        current_patient["name"] = name_match.group(1).strip()
                
                # Extract ward if we haven't yet
                if current_patient and "Ward" not in current_patient["info"]:
                    ward_match = re.search(r"Ward:\s*([^\n]+)", text)
                    if ward_match:
                        current_patient["info"]["Ward"] = ward_match.group(1).strip()
                
                # Extract DOB if we haven't yet
                if current_patient and "DOB" not in current_patient["info"]:
                    dob_match = re.search(r"DOB:\s*([^\n]+)", text)
                    if dob_match:
                        current_patient["info"]["DOB"] = dob_match.group(1).strip()
                
                # Check for care notes section
                if "Continuous Care Notes" in text and not in_care_notes:
                    in_care_notes = True
                
                # Extract care notes if we're in that section
                if in_care_notes and current_patient:
                    # If we're continuing from a previous page, just use the whole text
                    care_notes_text = text
                    if "Continuous Care Notes" in text:
                        # If this page has the header, extract notes from after that
                        care_notes_section = text.split("Continuous Care Notes", 1)
                        if len(care_notes_section) > 1:
                            care_notes_text = care_notes_section[1].strip()
                    else:
                        # If we're continuing from previous page, use the whole text
                        care_notes_text = text
                    
                    # Check if there's a header row on this page
                    if "Date & Time" in care_notes_text and "Staff Member" in care_notes_text and "Notes" in care_notes_text:
                        # Remove header row
                        header_pos = care_notes_text.find("Notes")
                        if header_pos > 0:
                            header_end = care_notes_text.find("\n", header_pos)
                            if header_end > 0:
                                care_notes_text = care_notes_text[header_end:].strip()
                    
                    # Now process the actual notes - try the long notes format first
                    care_notes_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+([^,]+(?:, [A-Z]+)?)\s+(.+?)(?=(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2})|$)"
                    matches = list(re.finditer(care_notes_pattern, care_notes_text, re.DOTALL))
                    if matches:
                        # Long notes format worked
                        for match in matches:
                            date = match.group(1).strip()
                            staff = match.group(2).strip()
                            note = match.group(3).strip()
                            if date and staff and note:
                                current_patient["care_notes"].append({
                                    "date": date,
                                    "staff": staff,
                                    "note": note
                                })
                    else:
                        # Try alternative format - splitting by lines and looking for date patterns
                        lines = care_notes_text.split('\n')
                        i = 0
                        while i < len(lines):
                            # Skip empty lines
                            if not lines[i].strip():
                                i += 1
                                continue
                            # Look for date time pattern at start of line
                            date_match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", lines[i].strip())
                            if date_match:
                                date = date_match.group(1)
                                # Extract rest of line after date
                                line_parts = lines[i][len(date):].strip().split("  ", 1)
                                if len(line_parts) > 1:
                                    staff = line_parts[0].strip()
                                    note_start = line_parts[1].strip()
                                    # Check for multi-line notes
                                    note_lines = [note_start]
                                    j = i + 1
                                    while j < len(lines) and not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", lines[j].strip()):
                                        if lines[j].strip():  # Only add non-empty lines
                                            note_lines.append(lines[j].strip())
                                        j += 1
                                    full_note = "\n".join(note_lines)
                                    current_patient["care_notes"].append({
                                        "date": date,
                                        "staff": staff,
                                        "note": full_note
                                    })
                                    i = j - 1  # Move to the last processed line
                            i += 1
        
        # Handle last patient
        if current_patient_id and current_patient:
            if not patient_id or current_patient_id == patient_id:
                patient_data[current_patient_id] = current_patient
        
        return patient_data
    
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

@lru_cache(maxsize=32)
def process_ward_pdf(pdf_path):
    """Process a ward PDF and extract patient data with robust error handling."""
    print(f"Processing PDF: {pdf_path}")
    patient_data = {}
    
    try:
        # Handle Google Drive file info dictionary
        if isinstance(pdf_path, dict):
            from app import get_drive_client
            if 'file_id' in pdf_path:
                try:
                    local_path = get_drive_client().get_local_path(pdf_path['file_id'], pdf_path['filename'])
                except Exception as e:
                    print(f"Error using drive_client.get_local_path: {str(e)}")
                    return {}
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
        
        # Try multiple methods to extract patient data
        patient_data = extract_patient_info(pdf_path)
        
        # If we couldn't extract data, try alternate methods
        if not patient_data:
            try:
                with fitz.open(pdf_path) as pdf:
                    toc = pdf.get_toc()
                    print(f"Trying alternative extraction - found {len(toc)} bookmarks")
                    
                    if len(toc) > 0:
                        # Extract from bookmarks
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
                                            "page": page - 1,  # Convert to 0-indexed
                                            "info": {},
                                            "vitals": "",
                                            "care_notes": []
                                        }
                                        print(f"Extracted patient: {name} ({patient_id})")
                                except Exception as e:
                                    print(f"Error processing bookmark '{title}': {str(e)}")
                    else:
                        # Try scanning text directly
                        patient_data = extract_patients_from_text(pdf)
            except Exception as e:
                print(f"Error during alternative extraction: {str(e)}")
                traceback.print_exc()
        
        print(f"Extracted {len(patient_data)} patients from PDF")
        return patient_data
        
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        traceback.print_exc()
        return {}
