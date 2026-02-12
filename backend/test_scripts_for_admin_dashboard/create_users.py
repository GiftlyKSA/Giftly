import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import User, Wallet
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
                    "phone_number": "555555556",
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
                    print(f"User with phone {user_data['phone_number']} already exists - updating if needed")
                    user = existing_user
                    # Update user data if needed
                    if not user.is_verified:
                        user.is_verified = True
                    if user.role != user_data["role"]:
                        user.role = user_data["role"]
                    if user_data["role"] == "Courier" and user.city_id != 1:
                        user.city_id = 1
                else:
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

                # Ensure user has a wallet
                wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
                existing_wallet = wallet_result.scalar_one_or_none()
                if not existing_wallet:
                    wallet = Wallet(user_id=user.id, balance=0)
                    db.add(wallet)
                    print(f"Created wallet for user {user_data['name']}")
                else:
                    print(f"Wallet already exists for user {user_data['name']}")

            await db.commit()
            print("All users created successfully")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_users())
