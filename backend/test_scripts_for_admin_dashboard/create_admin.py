import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import User
from auth import get_password_hash
from sqlalchemy import select

async def create_admin(username="admin", password="admin123"):
    # Validate password length (bcrypt limit is 72 characters)
    if len(password) > 72:
        print("Error: Password cannot be longer than 72 characters")
        return False

    async with AsyncSessionLocal() as db:
        try:
            # Check if admin already exists
            result = await db.execute(select(User).where(User.admin_username == username))
            existing_admin = result.scalar_one_or_none()
            if existing_admin:
                print(f"Admin user '{username}' already exists")
                return False

            # Create admin user
            hashed_password = get_password_hash(password)
            admin_user = User(
                phone_number=f"admin_{username}",  # dummy phone number
                name=f"Administrator {username}",
                is_admin=True,
                role='Admin',
                admin_username=username,
                admin_password_hash=hashed_password,
                is_verified=True
            )
            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)
            print(f"Admin user '{username}' created successfully")
            return True
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()
            return False

if __name__ == "__main__":
    # Allow command line arguments: python create_admin.py [username] [password]
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123"

    success = asyncio.run(create_admin(username, password))
    sys.exit(0 if success else 1)
