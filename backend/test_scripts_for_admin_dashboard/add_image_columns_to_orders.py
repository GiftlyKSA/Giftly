#!/usr/bin/env python3
"""
Script to add image columns to the orders table.
This script adds image1_data, image2_data, and image3_data columns as BLOB fields.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def add_image_columns():
    """Add image columns to the orders table."""
    try:
        async with engine.begin() as conn:
            print("Adding image columns to orders table...")

            # Add image1_data column
            await conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS image1_data BYTEA;
            """))
            print("✓ Added image1_data column")

            # Add image2_data column
            await conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS image2_data BYTEA;
            """))
            print("✓ Added image2_data column")

            # Add image3_data column
            await conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS image3_data BYTEA;
            """))
            print("✓ Added image3_data column")

            print("✅ Successfully added all image columns to orders table!")

    except Exception as e:
        print(f"❌ Error adding image columns: {e}")
        raise


async def main():
    """Main function to run the migration."""
    print("Starting migration: Add image columns to orders table")
    print("=" * 50)

    try:
        await add_image_columns()
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        print(f"\n💥 Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())