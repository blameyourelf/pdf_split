import sys
import os
import re
from datetime import datetime
import logging
from PyPDF2 import PdfReader

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Patient, Note

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_notes_from_pdf(pdf_path):
    """Extract care notes from PDF with improved table parsing"""
    try:
        logger.info(f"Extracting notes from: {pdf_path}")
        reader = PdfReader(pdf_path)
        notes = []
        
        # Process each page in the PDF
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            logger.info(f"Processing page {page_num+1}, text length: {len(text)}")
            
            # Debug: First 200 chars of each page to see content structure
            logger.debug(f"Page {page_num+1} start: {text[:200]}")
            
            # Check if this page contains care notes
            if "Continuous Care Notes" in text:
                # Split into lines
                lines = text.split('\n')
                notes_section = False
                header_found = False
                
                for line in lines:
                    # Skip until we find "Continuous Care Notes" section
                    if "Continuous Care Notes" in line:
                        notes_section = True
                        logger.debug("Found 'Continuous Care Notes' section")
                        continue
                    
                    # Look for header row after finding notes section
                    if notes_section and not header_found and "Date & Time" in line and "Staff Member" in line:
                        header_found = True
                        logger.debug("Found header row")
                        continue
                    
                    # Now process actual note rows (after section and header are found)
                    if notes_section and header_found and line.strip():
                        # Try to match the date/time pattern at the start of the line
                        date_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
                        if date_match:
                            try:
                                # Get the datetime from the match
                                datetime_str = date_match.group(1)
                                
                                # Rest of the line after the datetime
                                remaining = line[len(datetime_str):].strip()
                                
                                # Extract staff name (usually appears next and ends with commas/spaces)
                                staff_parts = remaining.split('  ')[0].strip()
                                # Get the actual note text (everything after staff name)
                                note_text = remaining[len(staff_parts):].strip()
                                
                                # Only add if we have valid data
                                if datetime_str and staff_parts and note_text:
                                    notes.append({
                                        'timestamp': datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'),
                                        'staff_name': staff_parts,
                                        'note_text': note_text
                                    })
                                    logger.debug(f"Extracted note: {datetime_str} | {staff_parts[:20]} | {note_text[:30]}...")
                            except Exception as e:
                                logger.error(f"Error parsing note line: {line[:50]}... Error: {str(e)}")
        
        logger.info(f"Successfully extracted {len(notes)} notes from PDF")
        return notes
        
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {str(e)}")
        return []