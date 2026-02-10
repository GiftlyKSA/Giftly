import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_courier_balance_and_user_fields():
    """
    Add new fields to users table and create courier_balance_additions table.
    This script adds national_id, passport_id to users table and creates the courier balance tracking table.
    """
    try:
        print("Starting migration for courier balance additions and user fields...")

        async with engine.begin() as conn:
            # Add new fields to users table
            print("Adding national_id and passport_id to users table...")
            await conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS national_id VARCHAR(255);
            """))

            await conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS passport_id VARCHAR(255);
            """))

            # Create courier_balance_additions table
            print("Creating courier_balance_additions table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS courier_balance_additions (
                    id SERIAL PRIMARY KEY,
                    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    payment_method VARCHAR(20) NOT NULL,
                    balance_before INTEGER NOT NULL,
                    amount_to_add INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create indexes for courier_balance_additions table
            print("Creating courier_balance_additions indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_balance_addition_invoice ON courier_balance_additions(invoice_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_balance_addition_order ON courier_balance_additions(order_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_balance_addition_user ON courier_balance_additions(user_id, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_balance_addition_created ON courier_balance_additions(created_at);"))

            # Add wallet_balance_before to payments table if it doesn't exist
            print("Adding wallet_balance_before to payments table...")
            await conn.execute(text("""
                ALTER TABLE payments
                ADD COLUMN IF NOT EXISTS wallet_balance_before INTEGER;
            """))

        print("\n🎉 Migration completed successfully!")
        print("\n📊 Changes made:")
        print("  • Added national_id column to users table")
        print("  • Added passport_id column to users table")
        print("  • Created courier_balance_additions table")
        print("  • Added wallet_balance_before column to payments table")
        print("  • Created all necessary indexes")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_courier_balance_and_user_fields())