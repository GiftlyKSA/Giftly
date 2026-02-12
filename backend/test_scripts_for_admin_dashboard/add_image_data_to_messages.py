#!/usr/bin/env python3
"""
Script to add image_data column to the messages table.
This script adds image_data column as a BLOB field for storing images in chat messages.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def add_image_data_column():
    """Add image_data column to the messages table."""
    try:
        async with engine.begin() as conn:
            print("Adding image_data column to messages table...")

            # Add image_data column
            await conn.execute(text("""
                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS image_data BYTEA;
            """))
            print("✓ Added image_data column to messages table")

            print("✅ Successfully added image_data column to messages table!")

    except Exception as e:
        print(f"❌ Error adding image_data column: {e}")
        raise


async def main():
    """Main function to run the migration."""
    print("Starting migration: Add image_data column to messages table")
    print("=" * 55)

    try:
        await add_image_data_column()
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        print(f"\n💥 Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())