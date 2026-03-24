import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_courier_reviews_table():
    """
    Create database table for courier reviews.
    This script creates the courier_reviews table and its indexes.
    """
    try:
        print("Starting creation of courier_reviews table...")

        async with engine.begin() as conn:
            # Create courier_reviews table
            print("Creating courier_reviews table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS courier_reviews (
                    id SERIAL PRIMARY KEY,
                    reviewed_by INTEGER NOT NULL REFERENCES users(id),
                    reviewed INTEGER NOT NULL REFERENCES users(id),
                    rate INTEGER NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP
                );
            """))

            # Create indexes for courier_reviews table
            print("Creating courier_reviews indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_review_reviewer ON courier_reviews(reviewed_by, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_review_reviewed ON courier_reviews(reviewed, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_courier_review_rate ON courier_reviews(rate);"))

        print("\n🎉 Courier reviews table and indexes created successfully!")
        print("\n📊 New table added:")
        print("  • courier_reviews - Customer reviews for couriers")

    except Exception as e:
        print(f"❌ Error creating courier_reviews table: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_courier_reviews_table())
