from app import app, db
from models import User, Settings, TemplateCategory, NoteTemplate, Ward
from sqlalchemy import inspect

def verify_initialization():
    """Verify that all system components are properly initialized"""
    with app.app_context():
        # Check database tables
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\nDatabase tables: {', '.join(tables)}")
        
        # Check users
        admin = User.query.filter_by(username='admin').first()
        nurse = User.query.filter_by(username='nurse1').first()
        print(f"\nAdmin user exists: {admin is not None}")
        print(f"Test nurse exists: {nurse is not None}")
        
        # Check settings
        settings = Settings.query.all()
        print(f"\nSystem settings:")
        for setting in settings:
            print(f"- {setting.key}: {setting.value}")
        
        # Check template categories
        categories = TemplateCategory.query.all()
        print(f"\nTemplate categories ({len(categories)}):")
        for category in categories:
            print(f"- {category.name}")
        
        # Check templates
        templates = NoteTemplate.query.all()
        print(f"\nNote templates: {len(templates)}")
        
        # Check wards
        wards = Ward.query.all()
        print(f"\nConfigured wards: {len(wards)}")
        for ward in wards:
            print(f"- Ward {ward.ward_number}: {ward.display_name}")

if __name__ == "__main__":
    verify_initialization()
