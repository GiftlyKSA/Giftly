import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import Admin
from auth import get_password_hash
from sqlalchemy import select

async def check_and_create_admin():
    async with AsyncSessionLocal() as db:
        try:
            # Check if admin already exists
            result = await db.execute(select(Admin).where(Admin.username == "admin"))
            existing_admin = result.scalar_one_or_none()
            if existing_admin:
                print("Admin 'admin' already exists - skipping creation")
                return True

            # Validate password length (bcrypt limit is 72 bytes)
            password = "admin123"
            if len(password.encode('utf-8')) > 72:
                print("Error: Default admin password is too long")
                return False

            # Create admin
            hashed_password = get_password_hash(password)
            admin = Admin(
                username="admin",
                password_hash=hashed_password,
                name="Administrator",
                email="admin@hadiyati.com",
                is_active=True
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            print("Admin 'admin' created successfully with password 'admin123'")
            return True
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()
            return False

if __name__ == "__main__":
    success = asyncio.run(check_and_create_admin())
    sys.exit(0 if success else 1)