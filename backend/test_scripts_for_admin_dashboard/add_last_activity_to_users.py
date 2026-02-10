import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from sqlalchemy import text

async def add_last_activity_column():
    """
    Add last_activity column to users table.
    This column tracks when users were last active for session management.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Check if column already exists
            result = await db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'last_activity'
            """))

            if result.fetchone():
                print("Column 'last_activity' already exists in users table")
                return

            # Add the column
            await db.execute(text("""
                ALTER TABLE users
                ADD COLUMN last_activity TIMESTAMP
            """))

            await db.commit()
            print("Successfully added 'last_activity' column to users table")

        except Exception as e:
            print(f"Error adding column: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(add_last_activity_column())