from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
import os
from datetime import datetime

app = Flask(__name__)
# Use a fixed SECRET_KEY for session management
app.config['SECRET_KEY'] = 'your-super-secret-key-8712'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

# Audit Log Model
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    patient_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def log_access(action, patient_id=None):
    if current_user.is_authenticated:
        log = AuditLog(
            user_id=current_user.id,
            action=action,
            patient_id=patient_id
        )
        db.session.add(log)
        db.session.commit()

# Dictionary to store ward data
wards_data = {}

def extract_patient_info(pdf_path):
    patient_data = {}
    current_patient = None
    current_info = []
    
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        text = page.extract_text()
        lines = text.split('\n')
        
        for line in lines:
            if line.startswith("Patient ID:"):
                if current_patient:
                    patient_data[current_patient] = {
                        "info": "\n".join(current_info),
                        "name": next((l.split(": ")[1] for l in current_info if l.startswith("Name:")), "Unknown"),
                        "ward": next((l.split(": ")[1] for l in current_info if l.startswith("Ward:")), "Unknown")
                    }
                current_patient = line.split(": ")[1]
                current_info = [line]
            else:
                if current_patient:
                    current_info.append(line)
        
        if current_patient:
            patient_data[current_patient] = {
                "info": "\n".join(current_info),
                "name": next((l.split(": ")[1] for l in current_info if l.startswith("Name:")), "Unknown"),
                "ward": next((l.split(": ")[1] for l in current_info if l.startswith("Ward:")), "Unknown")
            }
    
    return patient_data

# Load all ward PDFs
def load_ward_data():
    global wards_data
    wards_data.clear()
    for ward_num in range(1, 4):
        pdf_filename = f"ward_{ward_num}_records.pdf"
        if os.path.exists(pdf_filename):
            wards_data[str(ward_num)] = {
                "filename": pdf_filename,
                "patients": extract_patient_info(pdf_filename)
            }

# Load ward data when the application starts
load_ward_data()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            log_access('login')
            return redirect(url_for('index'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_access('logout')
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    load_ward_data()
    log_access('view_wards')
    return render_template('index.html', wards=wards_data)

@app.route('/ward/<ward_num>')
@login_required
def ward(ward_num):
    if ward_num in wards_data:
        log_access('view_ward', f'Ward {ward_num}')
        return render_template('ward.html', 
                            ward_num=ward_num, 
                            ward_data=wards_data[ward_num],
                            pdf_filename=wards_data[ward_num]["filename"])
    return "Ward not found", 404

@app.route('/search/<ward_num>')
@login_required
def search(ward_num):
    if ward_num not in wards_data:
        return jsonify([])
    
    search_query = request.args.get('q', '')
    ward_patients = wards_data[ward_num]["patients"]
    results = [{"id": pid, "name": data["name"]} 
              for pid, data in ward_patients.items() 
              if search_query in pid]
    return jsonify(results)

@app.route('/patient/<patient_id>')
@login_required
def patient(patient_id):
    for ward_num, ward_info in wards_data.items():
        if patient_id in ward_info["patients"]:
            patient_info = ward_info["patients"][patient_id]
            log_access('view_patient', patient_id)
            return render_template('patient.html',
                                patient_id=patient_id,
                                patient_info=patient_info["info"],
                                patient_name=patient_info["name"],
                                ward_num=ward_num,
                                pdf_filename=ward_info["filename"])
    
    return "Patient not found", 404

@app.route('/audit-log')
@login_required
def view_audit_log():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('audit_log.html', logs=logs)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
        # Create test user if not exists
        if not User.query.filter_by(username='nurse1').first():
            test_user = User(
                username='nurse1',
                password_hash=generate_password_hash('nurse123'),
                role='user'
            )
            db.session.add(test_user)
            
        db.session.commit()
    app.run(debug=True)
