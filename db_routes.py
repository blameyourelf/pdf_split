import json
import logging
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import desc, or_
from datetime import datetime, timedelta

# Import our modules
from database_schema import Ward, Patient, CareNote
from db_manager import db_manager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_routes.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create Blueprint for database routes
db_routes = Blueprint('db_routes', __name__)

@db_routes.route('/api/wards')
def get_wards():
    """Get all wards from the database."""
    try:
        with db_manager.session_scope() as session:
            wards = session.query(Ward).all()
            result = []
            
            for ward in wards:
                # Count patients in this ward
                patient_count = session.query(Patient).filter_by(ward_id=ward.id).count()
                
                result.append({
                    'id': ward.id,
                    'display_name': ward.display_name,
                    'filename': ward.filename,
                    'file_id': ward.file_id,
                    'last_updated': ward.last_updated.isoformat() if ward.last_updated else None,
                    'patient_count': patient_count
                })
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting wards: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_routes.route('/api/ward/<ward_id>/patients')
def get_ward_patients(ward_id):
    """Get all patients in a ward."""
    try:
        with db_manager.session_scope() as session:
            # Get the ward
            ward = session.query(Ward).filter_by(id=ward_id).first()
            if not ward:
                return jsonify({'error': 'Ward not found'}), 404
                
            # Get patients in this ward
            patients = session.query(Patient).filter_by(ward_id=ward_id).all()
            result = []
            
            for patient in patients:
                # Parse additional info JSON
                try:
                    additional_info = json.loads(patient.additional_info) if patient.additional_info else {}
                except json.JSONDecodeError:
                    additional_info = {}
                
                result.append({
                    'id': patient.id,
                    'name': patient.name,
                    'dob': patient.dob,
                    'age': patient.age,
                    'gender': patient.gender,
                    'pdf_page': patient.pdf_page,
                    'vitals': patient.vitals,
                    'additional_info': additional_info
                })
            
            return jsonify({
                'ward': {
                    'id': ward.id,
                    'display_name': ward.display_name,
                    'filename': ward.filename,
                    'last_updated': ward.last_updated.isoformat() if ward.last_updated else None
                },
                'patients': result
            })
    except Exception as e:
        logger.error(f"Error getting patients for ward {ward_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_routes.route('/api/patient/<patient_id>')
def get_patient(patient_id):
    """Get patient details by ID."""
    try:
        with db_manager.session_scope() as session:
            # Get the patient
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if not patient:
                return jsonify({'error': 'Patient not found'}), 404
            
            # Get the ward
            ward = session.query(Ward).filter_by(id=patient.ward_id).first()
            ward_info = {
                'id': ward.id,
                'display_name': ward.display_name
            } if ward else {'id': patient.ward_id, 'display_name': f'Ward {patient.ward_id}'}
            
            # Parse additional info JSON
            try:
                additional_info = json.loads(patient.additional_info) if patient.additional_info else {}
            except json.JSONDecodeError:
                additional_info = {}
            
            # Get care notes with pagination support
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 50))  # Default 50 notes per page
            offset = (page - 1) * limit
            
            # Get the total count
            total_notes = session.query(CareNote).filter_by(patient_id=patient_id).count()
            
            # Get the notes for this page
            care_notes = session.query(CareNote).filter_by(patient_id=patient_id)\
                .order_by(desc(CareNote.timestamp))\
                .offset(offset).limit(limit).all()
                
            notes_result = []
            for note in care_notes:
                notes_result.append({
                    'id': note.id,
                    'timestamp': note.timestamp.isoformat(),
                    'staff': note.staff,
                    'note': note.note,
                    'is_pdf_note': note.is_pdf_note
                })
            
            # Prepare the result
            result = {
                'id': patient.id,
                'name': patient.name,
                'dob': patient.dob,
                'age': patient.age,
                'gender': patient.gender,
                'ward': ward_info,
                'pdf_page': patient.pdf_page,
                'vitals': patient.vitals,
                'additional_info': additional_info,
                'care_notes': {
                    'total': total_notes,
                    'page': page,
                    'limit': limit,
                    'notes': notes_result,
                    'has_more': total_notes > (offset + limit)
                }
            }
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting patient {patient_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_routes.route('/api/patient/<patient_id>/notes')
def get_patient_notes(patient_id):
    """Get care notes for a patient with pagination."""
    try:
        with db_manager.session_scope() as session:
            # Check if patient exists
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if not patient:
                return jsonify({'error': 'Patient not found'}), 404
            
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 50))
            offset = (page - 1) * limit
            
            # Get the total count
            total_notes = session.query(CareNote).filter_by(patient_id=patient_id).count()
            
            # Get the notes for this page
            care_notes = session.query(CareNote).filter_by(patient_id=patient_id)\
                .order_by(desc(CareNote.timestamp))\
                .offset(offset).limit(limit).all()
                
            notes_result = []
            for note in care_notes:
                notes_result.append({
                    'id': note.id,
                    'timestamp': note.timestamp.isoformat(),
                    'staff': note.staff,
                    'note': note.note,
                    'is_pdf_note': note.is_pdf_note
                })
            
            return jsonify({
                'patient_id': patient_id,
                'patient_name': patient.name,
                'total': total_notes,
                'page': page,
                'limit': limit,
                'notes': notes_result,
                'has_more': total_notes > (offset + limit)
            })
    except Exception as e:
        logger.error(f"Error getting notes for patient {patient_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_routes.route('/api/search')
def search_patients():
    """Search patients by ID, name, or other fields."""
    try:
        # Get search term
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query too short'}), 400
        
        with db_manager.session_scope() as session:
            # Search for patients matching the query
            search_term = f"%{query}%"
            patients = session.query(Patient).filter(
                or_(
                    Patient.id.like(search_term),
                    Patient.name.like(search_term)
                )
            ).limit(100).all()  # Limit to 100 results for performance
            
            result = []
            for patient in patients:
                # Get ward name
                ward = session.query(Ward).filter_by(id=patient.ward_id).first()
                ward_name = ward.display_name if ward else f"Ward {patient.ward_id}"
                
                result.append({
                    'id': patient.id,
                    'name': patient.name,
                    'ward_id': patient.ward_id,
                    'ward_name': ward_name,
                    'dob': patient.dob,
                    'age': patient.age
                })
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error searching patients: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_routes.route('/api/ward/<ward_id>/search')
def search_ward_patients(ward_id):
    """Search patients within a specific ward."""
    try:
        # Get search term
        query = request.args.get('q', '').strip()
        
        with db_manager.session_scope() as session:
            # Check if ward exists
            ward = session.query(Ward).filter_by(id=ward_id).first()
            if not ward:
                return jsonify({'error': 'Ward not found'}), 404
                
            # Base query filters by ward
            base_query = session.query(Patient).filter_by(ward_id=ward_id)
            
            # If search term provided, filter further
            if query and len(query) >= 2:
                search_term = f"%{query}%"
                patients = base_query.filter(
                    or_(
                        Patient.id.like(search_term),
                        Patient.name.like(search_term)
                    )
                ).all()
            else:
                # Return all patients in the ward
                patients = base_query.all()
            
            result = []
            for patient in patients:
                result.append({
                    'id': patient.id,
                    'name': patient.name,
                    'dob': patient.dob,
                    'age': patient.age
                })
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error searching patients in ward {ward_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

def register_routes(app):
    """Register database routes with the Flask app."""
    app.register_blueprint(db_routes)
    logger.info("Database routes registered")
