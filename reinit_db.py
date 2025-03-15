from app import app, db

if __name__ == "__main__":
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        print("Creating audit tables...")
        db.create_all(bind=['audit'])
        print("Database reinitialized!")
