import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from models import User
from auth import create_jwt_tokens_async
from sqlalchemy import select

async def create_courier_token():
    async with AsyncSessionLocal() as db:
        try:
            # Find a courier user (preferably one assigned to Odai's order)
            # First, find Odai
            result = await db.execute(select(User).where(User.name == "Odai"))
            customer = result.scalar_one_or_none()

            courier = None
            if customer:
                # Find conversations where Odai is customer
                from models import Conversation
                result = await db.execute(select(Conversation).where(Conversation.customer_id == customer.id))
                conversation = result.scalar_one_or_none()
                if conversation:
                    # Get the courier from the conversation
                    result = await db.execute(select(User).where(User.id == conversation.courier_id))
                    courier = result.scalar_one_or_none()

            if not courier:
                # Find any courier user
                result = await db.execute(select(User).where(User.role == "Courier"))
                courier = result.scalar_one_or_none()

            if not courier:
                print("No courier user found. Please create a courier user first.")
                return

            print(f"Found courier: {courier.name} (ID: {courier.id})")

            # Create JWT tokens for the courier
            access_token, refresh_token = await create_jwt_tokens_async(db, courier)

            print(f"Created tokens for courier {courier.name}")
            print(f"Access Token: {access_token}")
            print(f"Refresh Token: {refresh_token}")
            print("\nYou can now run the send_courier_message.py script")

        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_courier_token())
