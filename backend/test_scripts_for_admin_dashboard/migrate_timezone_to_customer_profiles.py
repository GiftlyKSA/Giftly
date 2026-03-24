import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from sqlalchemy import text

async def migrate_timezone_data():
    """
    Migrate existing timezone data from users table to customer_profiles table.
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

            # Check if customer_profiles table exists
            result = await db.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'customer_profiles'
            """))

            if not result.fetchone():
                print("customer_profiles table does not exist. Please run create_customer_profiles_table.py first")
                return

            # Get users with timezone data
            result = await db.execute(text("""
                SELECT id, timezone FROM users WHERE timezone IS NOT NULL
            """))

            users_with_timezone = result.fetchall()

            if not users_with_timezone:
                print("No users with timezone data found")
                return

            print(f"Found {len(users_with_timezone)} users with timezone data")

            # Insert into customer_profiles
            for user_id, timezone in users_with_timezone:
                # Check if customer profile already exists
                result = await db.execute(text("""
                    SELECT id FROM customer_profiles WHERE user_id = %s
                """), (user_id,))

                if result.fetchone():
                    # Update existing profile
                    await db.execute(text("""
                        UPDATE customer_profiles SET timezone = %s WHERE user_id = %s
                    """), (timezone, user_id))
                else:
                    # Create new profile
                    await db.execute(text("""
                        INSERT INTO customer_profiles (user_id, timezone) VALUES (%s, %s)
                    """), (user_id, timezone))

            await db.commit()
            print(f"Successfully migrated timezone data for {len(users_with_timezone)} users")

        except Exception as e:
            print(f"Error migrating data: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(migrate_timezone_data())