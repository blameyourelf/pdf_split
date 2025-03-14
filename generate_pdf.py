import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

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
    age = random.randint(20, 80)
    condition = random.choice(conditions)
    treatment = random.choice(treatments)
    
    patient_info = f"Patient ID: {patient_id}\n"
    patient_info += f"Name: {full_name}\n"
    patient_info += f"Ward: {ward_num}\n"
    patient_info += f"Age: {age}\n"
    patient_info += f"Primary Diagnosis: {condition}\n"
    patient_info += f"Treatment Plan: {treatment}\n"
    patient_info += f"Admission Date: 2024-{random.randint(1,3)}-{random.randint(1,28)}\n"
    patient_info += f"Expected Discharge: 2024-{random.randint(4,6)}-{random.randint(1,28)}\n\n"
    
    # Add more detailed medical information
    patient_info += f"Current Medications:\n"
    for _ in range(random.randint(1, 3)):
        patient_info += f"- {random.choice(medications)}\n"
    
    patient_info += f"\nVital Signs:\n{random.choice(vital_signs)}\n\n"
    
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

def create_pdf(file_path, ward_num):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    y_position = height - 50
    
    # Add ward header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_position, f"Ward {ward_num} - Patient Records")
    y_position -= 30
    
    c.setFont("Helvetica", 12)
    for i in range(10):
        patient_id = f"W{ward_num}-{random.randint(1000000000, 9999999999)}"
        patient_info = generate_patient_info(patient_id, ward_num)
        
        # Add bookmarks for navigation
        c.bookmarkPage(patient_id)
        c.addOutlineEntry(patient_id, patient_id, level=0)
        
        for line in patient_info.split("\n"):
            if y_position < 50:  # Create a new page if space is low
                c.showPage()
                y_position = height - 50
                c.setFont("Helvetica", 12)
            c.drawString(50, y_position, line)
            y_position -= 15
        
        y_position -= 30  # Add space between patients

    c.save()

if __name__ == "__main__":
    # Create PDFs for each ward
    for ward_num in range(1, 4):
        create_pdf(f"ward_{ward_num}_records.pdf", ward_num)