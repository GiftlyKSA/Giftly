from database import SessionLocal, engine, Base
from models import Admin

def reset_admin():
    """
    Delete existing admin and create a new one with fresh credentials.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Delete existing admin
        existing_admin = db.query(Admin).filter(Admin.username == "admin").first()
        if existing_admin:
            db.delete(existing_admin)
            db.commit()
            print("Existing admin deleted")

        # Create new admin with pre-hashed password (bcrypt hash for "admin")
        # Generated with passlib: $2b$12$Azz0dWcbYNROG6MmSnu6vuzHhs1xI1lmiwkw1rCg47MtPXnG1K8Ju
        hashed_password = "$2b$12$Azz0dWcbYNROG6MmSnu6vuzHhs1xI1lmiwkw1rCg47MtPXnG1K8Ju"
        admin = Admin(
            username="admin",
            password_hash=hashed_password,
            name="Administrator",
            email="admin@hadiyati.com",
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("New admin created successfully")
        print("Username: admin")
        print("Password: admin")

    except Exception as e:
        print(f"Error during admin reset: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Resetting admin account...")
    reset_admin()
    print("Admin reset completed!")