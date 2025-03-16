import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph  # add Paragraph import
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet  # add getSampleStyleSheet import
from datetime import datetime, timedelta

# Lists for generating more realistic dummy data
conditions = [
    "Hypertension", "Type 2 Diabetes", "Acute Bronchitis", "Major Depressive Disorder",
    "Osteoarthritis", "Pneumonia", "Chronic Heart Failure", "Asthma", "COPD",
    "Gastroesophageal Reflux Disease"
]

treatments = [
    "Medication Therapy", "Physical Therapy", "Respiratory Therapy",
    "Cognitive Behavioral Therapy", "Occupational Therapy", "Speech Therapy",
    "IV Antibiotics", "Oxygen Therapy", "Pain Management", "Dietary Modification"
]

medications = [
    "Lisinopril 10mg daily", "Metformin 500mg twice daily",
    "Albuterol inhaler as needed", "Sertraline 50mg daily",
    "Acetaminophen 500mg every 6 hours", "Omeprazole 20mg daily"
]

vital_signs = [
    f"BP: {random.randint(110,140)}/{random.randint(60,90)}, "
    f"HR: {random.randint(60,100)}, "
    f"RR: {random.randint(12,20)}, "
    f"Temp: {round(random.uniform(36.5,37.5),1)}°C, "
    f"O2 Sat: {random.randint(95,100)}%"
]

care_notes = [
    "Patient resting comfortably. Vitals stable.",
    "Medication administered as prescribed.",
    "Patient reports mild discomfort, pain managed with PRN medication.",
    "Physical therapy session completed, good progress noted.",
    "Patient participated in daily activities.",
    "Appetite improved, finished 75% of meal.",
    "Respiratory therapy completed, breath sounds clear.",
    "Family visit, patient in good spirits.",
    "Dressing change completed, wound healing well.",
    "Sleep pattern improved with new medication regimen."
]

staff_names = [
    "Emma Thompson, RN", "Michael Chen, RN", "Sarah Martinez, RN",
    "David Wilson, RN", "Lisa Anderson, NP", "John Davis, RN",
    "Maria Garcia, RN", "James Lee, RN", "Rachel Brown, NP",
    "Kevin Patel, RN"
]

def generate_progress_note():
    return f"""Progress Note:
Patient is {random.choice(['stable', 'improving', 'responding well to treatment', 'showing progress'])}. 
{random.choice([
    'Patient reports feeling better today.',
    'Patient experiencing mild discomfort.',
    'Patient sleeping well.',
    'Patient appetite improving.',
])}
{random.choice([
    'Continuing current treatment plan.',
    'Adjusting medication dosage.',
    'Monitoring response to therapy.',
    'Scheduled for follow-up tests.',
])}"""

def generate_patient_info(patient_id, ward_num):
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    
    full_name = f"{random.choice(first_names)} {random.choice(last_names)}"
    dob = f"{random.randint(1940, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    
    patient_info = f"Patient ID: {patient_id}\n"
    patient_info += f"Name: {full_name}\n"
    patient_info += f"Ward: {ward_num}\n"
    patient_info += f"DOB: {dob}\n\n"
    
    # Add progress notes
    patient_info += generate_progress_note() + "\n\n"
    
    patient_info += "Additional Notes:\n"
    patient_info += random.choice([
        "Patient requires assistance with daily activities.",
        "Patient is independent with activities of daily living.",
        "Patient participating in physical therapy sessions.",
        "Patient following dietary restrictions as prescribed."
    ])
    
    return patient_info

styles = getSampleStyleSheet()  # get default styles
normal_style = styles['Normal']  # choose a style to wrap the text

def generate_care_notes(num_entries=10):
    notes = []
    current_date = datetime.now()
    
    for _ in range(num_entries):
        date = current_date.strftime("%Y-%m-%d %H:%M")
        staff = random.choice(staff_names)
        note = random.choice(care_notes)
        # Use Paragraph for the note, ensuring it wraps
        wrapped_note = Paragraph(note, normal_style)
        notes.append([date, staff, wrapped_note])
        current_date -= timedelta(hours=random.randint(4, 12))
    
    return notes

def format_patient_info(patient_id, name, ward_num, age, condition, treatment):
    return [
        ["Patient Demographics", ""],
        ["Patient ID:", patient_id],
        ["Name:", name],
        ["Ward:", str(ward_num)],
        ["Age:", str(age)],
        ["Primary Diagnosis:", condition],
        ["Treatment Plan:", treatment]
    ]

def create_pdf(file_path, ward_num):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    margin = 50
    available_width = width - 2*margin
    
    for i in range(24):  # 24 patients per ward
        # Generate patient info
        patient_id = str(random.randint(1000000000, 9999999999))
        first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        dob = f"{random.randint(1940, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        
        # Add bookmark for navigation
        c.bookmarkPage(patient_id)
        c.addOutlineEntry(f"Patient: {name} ({patient_id})", patient_id, level=0)
        
        # Draw header
        y_position = height - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, y_position, f"Patient Record - Ward {ward_num}")
        y_position -= 30
        
        # Create patient info table
        info_data = [
            ["Patient ID:", patient_id],
            ["Name:", name],
            ["Ward:", str(ward_num)],
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
        
        # Create care notes table
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y_position, "Continuous Care Notes")
        y_position -= 20
        
        notes_data = [["Date & Time", "Staff Member", "Notes"]] + generate_care_notes()
        notes_table = Table(notes_data, colWidths=[120, 120, available_width-240])
        notes_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        
        w, h = notes_table.wrap(available_width, y_position)
        if y_position - h < margin:  # Check if we need a new page
            c.showPage()
            y_position = height - margin
        notes_table.drawOn(c, margin, y_position - h)
        
        c.showPage()  # Start a new page for next patient
    
    c.save()

if __name__ == "__main__":
    # Create PDFs for numbered wards (1-50)
    for ward_num in range(1, 51):
        create_pdf(f"ward_{ward_num}_records.pdf", str(ward_num))  # Just pass the number as display name

    # Create PDFs for special wards with non-numeric names
    special_wards = [
        "ACU",  # Acute Care Unit
        "CCU",  # Critical Care Unit
        "HDU",  # High Dependency Unit
        "ICU",  # Intensive Care Unit
        "MAU",  # Medical Assessment Unit
        "NICU", # Neonatal Intensive Care Unit
        "Maple",  # Named wards
        "Oak",
        "Pine",
        "Willow",
        "Sunflower",
        "Rose",
        "ED",  # Emergency Department
        "Maternity",
        "Pediatrics"
    ]

    for ward_name in special_wards:
        create_pdf(f"ward_{ward_name}_records.pdf", ward_name)  # Use clean name for display