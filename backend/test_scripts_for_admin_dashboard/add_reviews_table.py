import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_reviews_table():
    """
    Create database table for reviews.
    This script creates the reviews table and its indexes.
    """
    try:
        print("Starting creation of reviews table...")

        async with engine.begin() as conn:
            # Create reviews table
            print("Creating reviews table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    reviewed_by INTEGER NOT NULL REFERENCES users(id),
                    reviewed INTEGER NOT NULL REFERENCES users(id),
                    rate INTEGER NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create indexes for reviews table
            print("Creating reviews indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_reviewer ON reviews(reviewed_by, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_reviewed ON reviews(reviewed, created_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_rate ON reviews(rate);"))

        print("\n🎉 Reviews table and indexes created successfully!")
        print("\n📊 New table added:")
        print("  • reviews - Customer reviews for couriers")

    except Exception as e:
        print(f"❌ Error creating reviews table: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_reviews_table())