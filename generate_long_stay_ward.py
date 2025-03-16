import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph  # added Paragraph import
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet               # added stylesheet import
from datetime import datetime, timedelta

# Get the default style for wrapping
styles = getSampleStyleSheet()
normal_style = styles['Normal']

# Reuse basic patient data arrays from generate_pdf.py
staff_names = [
    "Emma Thompson, RN", "Michael Chen, RN", "Sarah Martinez, RN",
    "David Wilson, RN", "Lisa Anderson, NP", "John Davis, RN",
    "Maria Garcia, RN", "James Lee, RN", "Rachel Brown, NP",
    "Kevin Patel, RN"
]

# Extended care note templates for longer entries
long_care_notes = [
    """Patient continues to make steady progress with rehabilitation. Morning physical therapy session completed with good engagement. Patient reported mild discomfort during exercises but was able to complete full session. Pain managed effectively with prescribed medication. Encouraged deep breathing exercises between activities. Patient participated well in afternoon mobility exercises.""",
    
    """Comprehensive nursing assessment completed. All vital signs within normal parameters. Patient alert and oriented x3. Skin assessment reveals no areas of concern. Previously noted redness on sacrum completely resolved. Maintaining good oral intake and tolerating regular diet. Family visited this afternoon and patient's mood notably improved afterward.""",
    
    """Night shift report: Patient experienced periods of restlessness between 2300-0200. PRN medication administered at 2330 with good effect. Finally settled to sleep around 0200. Regular position changes maintained throughout night. No signs of distress noted. Vital signs remained stable.""",
    
    """Multidisciplinary team review completed. Current treatment plan discussed with patient who expressed understanding and agreement. Goals adjusted to reflect recent progress. Speech therapy reports improvement in swallowing function. Occupational therapy session focused on daily living activities with notable progress in independent dressing.""",
    
    """Patient required increased oxygen support during morning activities. Respiratory therapy attended and performed chest physiotherapy. Good response noted with improved breath sounds post-treatment. SpO2 levels returned to baseline. Will continue to monitor closely."""
]

# Generate a random paragraph by combining sentences
def generate_random_paragraph():
    sentences = [
        "Vital signs remain stable throughout shift.",
        "Patient comfortable at rest.",
        "Good response to prescribed medications.",
        "Maintaining adequate oral intake.",
        "Family present for support.",
        "Regular position changes maintained.",
        "Oxygen therapy continued as prescribed.",
        "Patient participating well in care activities.",
        "No new concerns reported.",
        "Will continue to monitor."
    ]
    return " ".join(random.choices(sentences, k=random.randint(3, 8)))

def generate_long_care_note():
    # Sometimes use a template, sometimes generate random content
    if random.random() < 0.3:
        return random.choice(long_care_notes)
    else:
        # Generate 1-3 paragraphs
        paragraphs = []
        for _ in range(random.randint(1, 3)):
            paragraphs.append(generate_random_paragraph())
        return "\n\n".join(paragraphs)

def generate_patient_stay_notes():
    notes = []
    current_date = datetime.now()
    
    # Determine if this is a long-stay patient (>30 days)
    is_long_stay = random.random() < 0.2  # 20% chance
    
    if is_long_stay:
        # Generate 30-60 days of notes
        days_admitted = random.randint(30, 60)
        notes_per_day = random.randint(3, 6)  # More notes per day for long-stay
    else:
        # Generate 1-5 days of notes
        days_admitted = random.randint(1, 5)
        notes_per_day = random.randint(2, 4)
    
    # Generate notes for each day
    for day in range(days_admitted):
        day_date = current_date - timedelta(days=day)
        
        # Generate multiple notes per day
        for _ in range(notes_per_day):
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            note_datetime = day_date.replace(hour=hour, minute=minute)
            
            staff = random.choice(staff_names)
            note = generate_long_care_note()
            # Convert note text into a Paragraph for proper wrapping
            wrapped_note = Paragraph(note, normal_style)
            
            notes.append([note_datetime.strftime("%Y-%m-%d %H:%M"), staff, wrapped_note])
    
    # Sort notes by datetime (newest first)
    notes.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M"), reverse=True)
    return notes

def generate_extended_patient_stay_notes():
    # Generate a random number of continuous care notes between 10 and 200 for a patient.
    num_notes = random.randint(10, 200)
    notes = []
    current_date = datetime.now()
    for _ in range(num_notes):
        # Random time within the past 90 days
        delta_minutes = random.randint(0, 60*24*90)
        note_datetime = current_date - timedelta(minutes=delta_minutes)
        staff = random.choice(staff_names)
        note = generate_long_care_note()
        wrapped_note = Paragraph(note, normal_style)
        notes.append([note_datetime.strftime("%Y-%m-%d %H:%M"), staff, wrapped_note])
    notes.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M"), reverse=True)
    return notes

def create_long_stay_pdf(file_path):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    margin = 50
    available_width = width - 2*margin
    
    for i in range(24):  # 24 patients per ward
        # ...existing patient info generation...
        patient_id = str(random.randint(1000000000, 9999999999))
        name = f"{random.choice(['James', 'Mary', 'John', 'Patricia', 'Robert'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'])}"
        dob = f"{random.randint(1940, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        
        # ...existing bookmark and header...
        c.bookmarkPage(patient_id)
        c.addOutlineEntry(f"Patient: {name} ({patient_id})", patient_id, level=0)
        
        y_position = height - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, y_position, "Patient Record - Ward Long")
        y_position -= 30
        
        # ...existing info table...
        info_data = [
            ["Patient ID:", patient_id],
            ["Name:", name],
            ["Ward:", "Long"],
            ["DOB:", dob]
        ]
        info_table = Table(info_data, colWidths=[150, available_width-150])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        w, h = info_table.wrap(available_width, y_position)
        info_table.drawOn(c, margin, y_position - h)
        y_position -= h + 30
        
        # Create care notes table header on the first page only
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y_position, "Continuous Care Notes")
        y_position -= 20
        
        # Get notes data and prepare for table creation
        all_notes = generate_patient_stay_notes()
        header_row = ["Date & Time", "Staff Member", "Notes"]
        col_widths = [100, 100, available_width-200]
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ])
        
        # Process notes in chunks to ensure proper pagination
        remaining_notes = all_notes[:]  # Make a copy of all notes
        first_chunk = True  # Flag to track if this is the first chunk
        
        while remaining_notes:
            # Calculate available space on current page
            if first_chunk:
                available_height = y_position - margin
            else:
                available_height = height - margin * 2
            
            # Start with header row only for the first chunk
            current_chunk = []
            if first_chunk:
                current_chunk = [header_row]
            
            # Add rows until we can't fit any more
            rows_to_remove = 0
            for i, note_row in enumerate(remaining_notes):
                if first_chunk:
                    # First chunk includes header
                    test_chunk = current_chunk + [note_row]
                else:
                    # Subsequent chunks don't include header
                    test_chunk = current_chunk + [note_row]
                
                test_table = Table(test_chunk, colWidths=col_widths)
                
                # Apply style - but with header styling only on first chunk
                if first_chunk:
                    test_table.setStyle(table_style)
                else:
                    # Remove header-specific styling for continuation chunks
                    cont_style = TableStyle([
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ])
                    test_table.setStyle(cont_style)
                
                w, h = test_table.wrap(available_width, height)
                
                if h <= available_height:
                    current_chunk.append(note_row)
                    rows_to_remove = i + 1
                else:
                    # If we couldn't add even one row, force at least one row
                    if len(current_chunk) == 0 and i == 0:
                        current_chunk.append(note_row)
                        rows_to_remove = 1
                    break
            
            # If we have rows to draw, create and draw the table
            if current_chunk:
                # Create the final table for this chunk
                if first_chunk:
                    chunk_table = Table([header_row] + current_chunk, colWidths=col_widths)
                    chunk_table.setStyle(table_style)
                else:
                    chunk_table = Table(current_chunk, colWidths=col_widths)
                    # Only apply non-header styles
                    cont_style = TableStyle([
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ])
                    chunk_table.setStyle(cont_style)
                
                w, h = chunk_table.wrap(available_width, available_height)
                
                # Ensure we have enough space or go to a new page
                if y_position - h < margin:
                    c.showPage()
                    y_position = height - margin
                
                chunk_table.drawOn(c, margin, y_position - h)
                y_position -= h
            
            # Remove processed rows
            remaining_notes = remaining_notes[rows_to_remove:]
            
            # If we have more notes, go to a new page
            if remaining_notes:
                c.showPage()
                y_position = height - margin
                
            # No longer the first chunk after the first iteration
            first_chunk = False
        
        c.showPage()  # Start new page for next patient
    
    c.save()

def create_extended_long_stay_pdf(file_path, ward_name):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    margin = 50
    available_width = width - 2*margin
    
    for i in range(24):  # 24 patients per ward
        # ...existing patient info generation...
        patient_id = str(random.randint(1000000000, 9999999999))
        name = f"{random.choice(['James','Mary','John','Patricia','Robert'])} {random.choice(['Smith','Johnson','Williams','Brown','Jones'])}"
        dob = f"{random.randint(1940,2000)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        
        # ...existing bookmark and header...
        c.bookmarkPage(patient_id)
        c.addOutlineEntry(f"Patient: {name} ({patient_id})", patient_id, level=0)
        
        y_position = height - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, y_position, f"Patient Record - Ward {ward_name}")
        y_position -= 30
        
        # ...existing info table...
        info_data = [
            ["Patient ID:", patient_id],
            ["Name:", name],
            ["Ward:", ward_name],
            ["DOB:", dob]
        ]
        info_table = Table(info_data, colWidths=[150, available_width - 150])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        w, h = info_table.wrap(available_width, y_position)
        info_table.drawOn(c, margin, y_position - h)
        y_position -= h + 30
        
        # Create care notes table header on the first page only
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y_position, "Continuous Care Notes")
        y_position -= 20
        
        # Get notes data and prepare for table creation
        all_notes = generate_extended_patient_stay_notes()
        header_row = ["Date & Time", "Staff Member", "Notes"]
        col_widths = [100, 100, available_width-200]
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ])
        
        # Process notes in chunks to ensure proper pagination
        remaining_notes = all_notes[:]  # Make a copy of all notes
        first_chunk = True  # Flag to track if this is the first chunk
        
        while remaining_notes:
            # Calculate available space on current page
            if first_chunk:
                available_height = y_position - margin
            else:
                available_height = height - margin * 2
            
            # Start with header row only for the first chunk
            current_chunk = []
            if first_chunk:
                current_chunk = [header_row]
            
            # Add rows until we can't fit any more
            rows_to_remove = 0
            for i, note_row in enumerate(remaining_notes):
                test_chunk = current_chunk + [note_row]
                test_table = Table(test_chunk, colWidths=col_widths)
                
                # Apply style - but with header styling only on first chunk
                if first_chunk:
                    test_table.setStyle(table_style)
                else:
                    # Remove header-specific styling for continuation chunks
                    cont_style = TableStyle([
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ])
                    test_table.setStyle(cont_style)
                
                w, h = test_table.wrap(available_width, height)
                
                if h <= available_height:
                    current_chunk.append(note_row)
                    rows_to_remove = i + 1
                else:
                    # If we couldn't add even one row, force at least one row
                    if len(current_chunk) == 0 and i == 0:
                        current_chunk.append(note_row)
                        rows_to_remove = 1
                    break
            
            # If we have rows to draw, create and draw the table
            if current_chunk:
                # Create the final table for this chunk
                chunk_table = Table(current_chunk, colWidths=col_widths)
                if first_chunk:
                    chunk_table.setStyle(table_style)
                else:
                    # Only apply non-header styles
                    cont_style = TableStyle([
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ])
                    chunk_table.setStyle(cont_style)
                
                w, h = chunk_table.wrap(available_width, available_height)
                
                # Ensure we have enough space or go to a new page
                if y_position - h < margin:
                    c.showPage()
                    y_position = height - margin
                
                chunk_table.drawOn(c, margin, y_position - h)
                y_position -= h
            
            # Remove processed rows
            remaining_notes = remaining_notes[rows_to_remove:]
            
            # If we have more notes, go to a new page
            if remaining_notes:
                c.showPage()
                y_position = height - margin
                
            # No longer the first chunk after the first iteration
            first_chunk = False
        
        c.showPage()  # Start new page for next patient
    
    c.save()

if __name__ == "__main__":
    create_long_stay_pdf("ward_Long_records.pdf")
    print("Generated long-stay ward PDF with extended care notes")
    
    # Create 10 new long stay wards with unique names
    new_long_wards = [f"Long_{i}" for i in range(1, 11)]
    for ward in new_long_wards:
        create_extended_long_stay_pdf(f"ward_{ward}_records.pdf", ward)
    print("Generated long-stay ward PDFs with extended care notes")
