from app import app, db
from models import NoteTemplate, TemplateCategory
from sqlalchemy import inspect, text
import sys

def setup_template_categories():
    """Create template categories and add category_id to NoteTemplate"""
    with app.app_context():
        try:
            # Check if table exists
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            columns = {col['name'] for col in inspector.get_columns('note_template')} if 'note_template' in tables else set()
            
            print("Starting template categories migration...")
            
            # Create the template_category table if it doesn't exist
            if 'template_category' not in tables:
                print("Creating template_category table...")
                db.engine.execute('''
                CREATE TABLE template_category (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE
                )
                ''')
                
                # Add default categories
                default_categories = [
                    "Medical", "Nursing", "Surgical", "Admin",
                    "Emergency", "Pediatric", "Geriatric", "Psychiatric",
                    "Obstetric", "Oncology", "Cardiology", "Neurology"
                ]
                
                for category in default_categories:
                    db.engine.execute(
                        text("INSERT INTO template_category (name) VALUES (:name)"),
                        {"name": category}
                    )
                
                print(f"Added {len(default_categories)} default categories")
            
            # Add category_id column to note_template if not present
            if 'note_template' in tables and 'category_id' not in columns:
                print("Adding category_id column to note_template table...")
                db.engine.execute('ALTER TABLE note_template ADD COLUMN category_id INTEGER')
                
                # Map existing text categories to category IDs for existing templates
                templates_with_categories = db.engine.execute(
                    'SELECT id, category FROM note_template WHERE category IS NOT NULL'
                ).fetchall()
                
                print(f"Found {len(templates_with_categories)} templates with categories to update")
                
                for template_id, category_text in templates_with_categories:
                    if category_text:
                        # Check if category exists
                        category = db.engine.execute(
                            text("SELECT id FROM template_category WHERE name = :name"),
                            {"name": category_text}
                        ).fetchone()
                        
                        # If not, create it
                        if not category:
                            db.engine.execute(
                                text("INSERT INTO template_category (name) VALUES (:name)"),
                                {"name": category_text}
                            )
                            category = db.engine.execute(
                                text("SELECT id FROM template_category WHERE name = :name"),
                                {"name": category_text}
                            ).fetchone()
                        
                        # Update the template with the category ID
                        db.engine.execute(
                            text("UPDATE note_template SET category_id = :category_id WHERE id = :template_id"),
                            {"category_id": category[0], "template_id": template_id}
                        )
                
                print("Migration completed successfully!")
            else:
                if 'category_id' in columns:
                    print("category_id column already exists in note_template table")
                if 'template_category' in tables:
                    print("template_category table already exists")
                
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    setup_template_categories()
