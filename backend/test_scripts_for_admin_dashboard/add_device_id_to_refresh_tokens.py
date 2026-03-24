import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_device_id_to_refresh_tokens():
    """
    Add device_id column to refresh_tokens table.
    This script adds the device_id column to support device-specific refresh tokens.
    """
    try:
        print("Starting addition of device_id column to refresh_tokens table...")

        async with engine.begin() as conn:
            # Add device_id column to refresh_tokens table
            print("Adding device_id column to refresh_tokens table...")
            await conn.execute(text("""
                ALTER TABLE refresh_tokens
                ADD COLUMN IF NOT EXISTS device_id VARCHAR(255);
            """))

            # Add index for device_id
            print("Adding index for device_id...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_refresh_device ON refresh_tokens(user_id, device_id);"))

        print("\n🎉 Device ID column added to refresh_tokens table successfully!")
        print("\n📊 Updated table:")
        print("  • refresh_tokens - Added device_id column and index")

    except Exception as e:
        print(f"❌ Error adding column: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_device_id_to_refresh_tokens())