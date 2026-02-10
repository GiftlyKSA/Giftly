import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_deposit_requests_table():
    """
    Create database table for deposit requests by couriers.
    This script creates the deposit_requests table with all required columns and indexes.
    """
    try:
        print("Starting creation of deposit_requests table...")

        async with engine.begin() as conn:
            # Create deposit_requests table
            print("Creating deposit_requests table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS deposit_requests (
                    id SERIAL PRIMARY KEY,
                    courier_id INTEGER NOT NULL REFERENCES users(id),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    amount INTEGER NOT NULL,
                    wallet_balance_before INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create indexes for deposit_requests table
            print("Creating deposit_requests indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deposit_request_courier ON deposit_requests(courier_id, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deposit_request_status ON deposit_requests(status, created_at);"))

        print("\n🎉 Deposit requests table created successfully!")
        print("\n📊 New table added:")
        print("  • deposit_requests - Courier wallet deposit requests")
        print("\n📋 Columns:")
        print("  • courier_id - Reference to the courier user")
        print("  • status - Request status (pending/approved/rejected)")
        print("  • amount - Requested amount in cents/halaym")
        print("  • wallet_balance_before - Wallet balance before request")
        print("  • created_at - Request creation timestamp")
        print("  • updated_at - Request update timestamp")

    except Exception as e:
        print(f"❌ Error creating deposit_requests table: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_deposit_requests_table())