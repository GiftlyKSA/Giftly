import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def migrate_new_models_defaults():
    """
    Migrate existing tables to use server-side defaults for datetime fields.
    This script updates the default values for created_at and updated_at columns
    in the new models (wallets, payments, promocodes) to use database defaults.
    """
    try:
        print("Starting migration of datetime defaults for new models...")

        async with engine.begin() as conn:
            # Update wallets table defaults
            print("Updating wallets table defaults...")
            await conn.execute(text("""
                ALTER TABLE wallets
                ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
                ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
            """))

            # Update payments table defaults
            print("Updating payments table defaults...")
            await conn.execute(text("""
                ALTER TABLE payments
                ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
                ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
            """))

            # Update promocodes table defaults
            print("Updating promocodes table defaults...")
            await conn.execute(text("""
                ALTER TABLE promocodes
                ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
                ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
            """))

            # Update conversations table defaults
            print("Updating conversations table defaults...")
            await conn.execute(text("""
                ALTER TABLE conversations
                ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
            """))

            # Update messages table defaults
            print("Updating messages table defaults...")
            await conn.execute(text("""
                ALTER TABLE messages
                ALTER COLUMN sent_at SET DEFAULT CURRENT_TIMESTAMP;
            """))

        print("\n🎉 Migration completed successfully!")
        print("\n📊 Updated tables:")
        print("  • wallets - created_at, updated_at now use CURRENT_TIMESTAMP default")
        print("  • payments - created_at, updated_at now use CURRENT_TIMESTAMP default")
        print("  • promocodes - created_at, updated_at now use CURRENT_TIMESTAMP default")
        print("  • conversations - created_at now uses CURRENT_TIMESTAMP default")
        print("  • messages - sent_at now uses CURRENT_TIMESTAMP default")
        print("\n💡 This ensures SQLAdmin compatibility by using database-side defaults")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        print("Make sure your database is running and the tables exist.")
        print("If tables don't exist yet, run add_new_models_tables.py first.")

if __name__ == "__main__":
    asyncio.run(migrate_new_models_defaults())