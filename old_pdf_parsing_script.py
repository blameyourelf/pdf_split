from PyPDF2 import PdfReader
import re

def extract_patient_info(pdf_path, patient_id=None):
    """Extract patient info and notes while supporting multiple note formats"""
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

def process_patient_data(info_lines):
    demographics = {}
    care_notes = []
    in_care_notes = False
    header_found = False
    try:
        for line in info_lines:
            line = line.strip()
            if not line:
                continue
            # Check for care notes section
            if "Continuous Care Notes" in line:
                in_care_notes = True
                continue
            # Skip the header row of the care notes table
            if in_care_notes and not header_found and "Date & Time" in line:
                header_found = True
                continue
            if not in_care_notes:
                # Process demographics fields
                fields = {
                    "Patient ID:": "Patient ID",
                    "Name:": "Name",
                    "Ward:": "Ward",
                    "DOB:": "DOB"
                }
                for prefix, key in fields.items():
                    if prefix in line:
                        value = line.split(prefix, 1)[1].strip()
                        demographics[key] = value
            elif in_care_notes and header_found:
                # Process care notes - expecting date, staff member, and note
                parts = [p.strip() for p in line.split("  ") if p.strip()]
                if len(parts) >= 3:
                    care_notes.append({
                        "date": parts[0],
                        "staff": parts[1],
                        "note": " ".join(parts[2:])
                    })
                elif len(parts) == 2:
                    care_notes.append({
                        "date": parts[0],
                        "staff": parts[1],
                        "note": ""
                    })
        # Ensure we have a name
        if "Name" not in demographics:
            demographics["Name"] = "Unknown"
        patient_data = {
            "info": demographics,
            "name": demographics.get("Name", "Unknown"),
            "vitals": "",
            "care_notes": care_notes
        }
        return patient_data
    except Exception as e:
        return {
            "info": {"Name": "Error Processing Patient"},
            "name": "Error Processing Patient",
            "vitals": "",
            "care_notes": []
        }