#!/usr/bin/env python3
"""
Script to change image columns from BYTEA to TEXT type in the orders and messages tables.
This allows storing base64 encoded images as strings.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def change_image_columns_to_text():
    """Change image columns from BYTEA to TEXT type."""
    try:
        async with engine.begin() as conn:
            print("Changing image columns from BYTEA to TEXT...")

            # Change orders table image columns to TEXT
            await conn.execute(text("""
                ALTER TABLE orders
                ALTER COLUMN image1_data TYPE TEXT;
            """))
            print("✓ Changed orders.image1_data to TEXT")

            await conn.execute(text("""
                ALTER TABLE orders
                ALTER COLUMN image2_data TYPE TEXT;
            """))
            print("✓ Changed orders.image2_data to TEXT")

            await conn.execute(text("""
                ALTER TABLE orders
                ALTER COLUMN image3_data TYPE TEXT;
            """))
            print("✓ Changed orders.image3_data to TEXT")

            # Change messages table image column to TEXT
            await conn.execute(text("""
                ALTER TABLE messages
                ALTER COLUMN image_data TYPE TEXT;
            """))
            print("✓ Changed messages.image_data to TEXT")

            print("✅ Successfully changed all image columns to TEXT type!")

    except Exception as e:
        print(f"❌ Error changing image columns: {e}")
        raise


async def main():
    """Main function to run the migration."""
    print("Starting migration: Change image columns from BYTEA to TEXT")
    print("=" * 60)

    try:
        await change_image_columns_to_text()
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        print(f"\n💥 Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())