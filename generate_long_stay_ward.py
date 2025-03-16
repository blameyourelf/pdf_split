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

def create_long_stay_pdf(file_path):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    margin = 50
    available_width = width - 2*margin
    
    for i in range(24):  # 24 patients per ward
        # Generate patient info (same as original script)
        patient_id = str(random.randint(1000000000, 9999999999))
        name = f"{random.choice(['James', 'Mary', 'John', 'Patricia', 'Robert'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'])}"
        dob = f"{random.randint(1940, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        
        # Add bookmark for navigation
        c.bookmarkPage(patient_id)
        c.addOutlineEntry(f"Patient: {name} ({patient_id})", patient_id, level=0)
        
        # Draw header
        y_position = height - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, y_position, "Patient Record - Ward Long")
        y_position -= 30
        
        # Create patient info table
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
        
        # Create care notes table with more extensive notes
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y_position, "Continuous Care Notes")
        y_position -= 20
        
        notes_data = [["Date & Time", "Staff Member", "Notes"]] + generate_patient_stay_notes()
        notes_table = Table(notes_data, colWidths=[100, 100, available_width-200])
        notes_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        # Instead of drawing the whole table at once, split it into fragments that fit.
        fragments = notes_table.split(available_width, y_position - margin)
        for frag in fragments:
            frag_w, frag_h = frag.wrap(available_width, y_position - margin)
            if y_position - frag_h < margin:
                c.showPage()
                y_position = height - margin
            frag.drawOn(c, margin, y_position - frag_h)
            y_position -= frag_h
        
        c.showPage()  # Start a new page for next patient
    
    c.save()

if __name__ == "__main__":
    create_long_stay_pdf("ward_Long_records.pdf")
    print("Generated long-stay ward PDF with extended care notes")
