import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import User, Wallet
from sqlalchemy import select

async def add_missing_wallets():
    async with AsyncSessionLocal() as db:
        try:
            # Get all users
            result = await db.execute(select(User))
            users = result.scalars().all()

            if not users:
                print("No users found.")
                return

            wallets_created = 0
            for user in users:
                # Check if wallet already exists for this user
                result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
                existing_wallet = result.scalar_one_or_none()
                if existing_wallet:
                    print(f"Wallet already exists for user {user.name} ({user.phone_number})")
                    continue

                # Create wallet with balance 0
                wallet = Wallet(
                    user_id=user.id,
                    balance=0
                )
                db.add(wallet)
                print(f"Created wallet for {user.name} ({user.role}) with balance 0 halaym")
                wallets_created += 1

            await db.commit()
            print(f"Successfully created {wallets_created} wallets for users who didn't have them")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(add_missing_wallets())