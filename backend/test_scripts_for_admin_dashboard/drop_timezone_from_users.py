import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from sqlalchemy import text

async def drop_timezone_column():
    """
    Drop timezone column from users table after migrating data to customer_profiles.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Check if timezone column exists in users table
            result = await db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'timezone'
            """))

            if not result.fetchone():
                print("Timezone column does not exist in users table")
                return

            # Drop the column
            await db.execute(text("""
                ALTER TABLE users DROP COLUMN timezone
            """))

            await db.commit()
            print("Successfully dropped 'timezone' column from users table")

        except Exception as e:
            print(f"Error dropping column: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(drop_timezone_column())