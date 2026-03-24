import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from sqlalchemy import text

async def create_customer_profiles_table():
    """
    Create customer_profiles table to store customer-specific data including timezone.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Check if table already exists
            result = await db.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'customer_profiles'
            """))

            if result.fetchone():
                print("Table 'customer_profiles' already exists")
                return

            # Create the table
            await db.execute(text("""
                CREATE TABLE customer_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                    timezone VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Create index
            await db.execute(text("""
                CREATE INDEX idx_customer_profile_user ON customer_profiles(user_id)
            """))

            await db.commit()
            print("Successfully created 'customer_profiles' table")

        except Exception as e:
            print(f"Error creating table: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_customer_profiles_table())