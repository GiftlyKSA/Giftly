import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_created_by_user_id_to_invoices():
    """
    Add created_by_user_id column to invoices table.
    This column tracks which user created the invoice.
    """
    try:
        print("Adding created_by_user_id column to invoices table...")

        async with engine.begin() as conn:
            # Add created_by_user_id column to invoices table if it doesn't exist
            print("Adding created_by_user_id to invoices table...")
            await conn.execute(text("""
                ALTER TABLE invoices
                ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id);
            """))

            # Create index for the new column
            print("Creating index for created_by_user_id...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_created_by ON invoices(created_by_user_id);"))

        print("✅ Successfully added created_by_user_id column to invoices table!")
        print("📊 New column added:")
        print("  • created_by_user_id - References users(id), tracks who created the invoice")

    except Exception as e:
        print(f"❌ Error adding column: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_created_by_user_id_to_invoices())