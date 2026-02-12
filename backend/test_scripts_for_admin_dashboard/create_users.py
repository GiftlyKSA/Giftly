import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import User
from datetime import date
from sqlalchemy import select

async def create_users():
    async with AsyncSessionLocal() as db:
        try:
            # Define users to create
            users_data = [
                {
                    "name": "Abdulrahman",
                    "phone_number": "555025551",
                    "email": "abdulrahman@example.com",
                    "date_of_birth": date(1990, 1, 1),
                    "role": "Customer"
                },
                {
                    "name": "Mohanned",
                    "phone_number": "553111551",
                    "email": "mohanned@example.com",
                    "date_of_birth": date(1990, 1, 2),
                    "role": "Customer"
                },
                {
                    "name": "Odai",
                    "phone_number": "559644339",
                    "email": "odai@example.com",
                    "date_of_birth": date(1990, 1, 3),
                    "role": "Customer"
                },
                {
                    "name": "Mohammed",
                    "phone_number": "551234567",
                    "email": "mohammed@example.com",
                    "date_of_birth": date(1990, 1, 4),
                    "role": "Courier",
                    
                }
            ]

            for user_data in users_data:
                # Check if user already exists by phone number
                result = await db.execute(select(User).where(User.phone_number == user_data["phone_number"]))
                existing_user = result.scalar_one_or_none()
                if existing_user:
                    print(f"User with phone {user_data['phone_number']} already exists")
                    continue

                # Create user
                user = User(
                    name=user_data["name"],
                    phone_number=user_data["phone_number"],
                    email=user_data["email"],
                    date_of_birth=user_data["date_of_birth"],
                    role=user_data["role"],
                    is_verified=True
                )
                if user_data["role"] == "Courier":
                    user.city_id = 1
                db.add(user)
                print(f"Created user {user_data['name']} with phone {user_data['phone_number']}")

            await db.commit()
            print("All users created successfully")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_users())
