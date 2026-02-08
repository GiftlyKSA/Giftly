import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def migrate_conversations_order():
    """
    Migrate conversations table to support order-based conversations.
    Adds order_id column and makes courier_id nullable.
    """
    try:
        print("Starting migration of conversations table...")

        async with engine.begin() as conn:
            # Add order_id column to conversations table
            print("Adding order_id column to conversations table...")
            await conn.execute(text("""
                ALTER TABLE conversations
                ADD COLUMN IF NOT EXISTS order_id INTEGER REFERENCES orders(id);
            """))

            # Make courier_id nullable
            print("Making courier_id nullable...")
            await conn.execute(text("""
                ALTER TABLE conversations
                ALTER COLUMN courier_id DROP NOT NULL;
            """))

            # Drop the old unique constraint
            print("Dropping old unique constraint...")
            try:
                await conn.execute(text("""
                    ALTER TABLE conversations
                    DROP CONSTRAINT IF EXISTS unique_customer_courier;
                """))
            except Exception as e:
                print(f"Note: Could not drop constraint (might not exist): {e}")

            # Add new unique constraint based on customer and order
            print("Adding new unique constraint...")
            await conn.execute(text("""
                ALTER TABLE conversations
                ADD CONSTRAINT unique_customer_order UNIQUE (customer_id, order_id);
            """))

            # Create indexes for the new structure
            print("Creating new indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversation_order ON conversations(order_id, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversation_status ON conversations(status, created_at);"))

        print("\n🎉 Conversations table migration completed successfully!")
        print("\n📊 Changes made:")
        print("  • Added order_id column (references orders.id)")
        print("  • Made courier_id nullable")
        print("  • Changed unique constraint from (customer_id, courier_id) to (customer_id, order_id)")
        print("  • Added new indexes for order_id and status")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(migrate_conversations_order())