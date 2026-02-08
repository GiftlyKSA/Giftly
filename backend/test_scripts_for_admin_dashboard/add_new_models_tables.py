import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_new_models_tables():
    """
    Create database tables for the new models: wallets, payments, and promocodes.
    This script creates the tables and their indexes for the new payment/wallet/promocode system.
    """
    try:
        print("Starting creation of new model tables...")

        async with engine.begin() as conn:
            # Create wallets table
            print("Creating wallets table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                    balance INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create payments table
            print("Creating payments table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    amount INTEGER NOT NULL,
                    payment_method VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    transaction_id VARCHAR(255),
                    payment_date TIMESTAMP,
                    payment_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create promocodes table
            print("Creating promocodes table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    code VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    percentage INTEGER NOT NULL,
                    max_value INTEGER NOT NULL DEFAULT 0,
                    minimum_order_value INTEGER NOT NULL DEFAULT 0,
                    usage_limit INTEGER NOT NULL DEFAULT 0,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    valid_until TIMESTAMP NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT true,
                    applicable_to VARCHAR(50) NOT NULL DEFAULT 'order_total',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Add promocode_id column to invoices table if it doesn't exist
            print("Adding promocode_id to invoices table...")
            await conn.execute(text("""
                ALTER TABLE invoices
                ADD COLUMN IF NOT EXISTS promocode_id INTEGER REFERENCES promocodes(id);
            """))

            # Create conversations table
            print("Creating conversations table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES users(id),
                    courier_id INTEGER NOT NULL REFERENCES users(id),
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(customer_id, courier_id)
                );
            """))

            # Create messages table
            print("Creating messages table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    sender_id INTEGER NOT NULL REFERENCES users(id),
                    content TEXT NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    message_type VARCHAR(20) NOT NULL DEFAULT 'text',
                    invoice_description TEXT,
                    invoice_gift_price INTEGER,
                    invoice_service_fee INTEGER,
                    invoice_delivery_fee INTEGER,
                    invoice_total INTEGER
                );
            """))

            # Create indexes for wallets table
            print("Creating wallets indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallets(user_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wallet_balance ON wallets(balance);"))

            # Create indexes for payments table
            print("Creating payments indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_invoice ON payments(invoice_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_user ON payments(user_id, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status, payment_date);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_method ON payments(payment_method, status);"))

            # Create indexes for promocodes table
            print("Creating promocodes indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_promocode_code ON promocodes(code);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_promocode_active ON promocodes(active, valid_until);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_promocode_valid ON promocodes(active, valid_until, usage_limit, usage_count);"))

        print("\n🎉 All new model tables and indexes created successfully!")
        print("\n📊 New tables added:")
        print("  • wallets - User wallet balances")
        print("  • payments - Payment transactions")
        print("  • promocodes - Discount codes")
        print("  • conversations - Chat conversations")
        print("  • messages - Chat messages")
        print("  • Updated invoices table with promocode support")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_new_models_tables())