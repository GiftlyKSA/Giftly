import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import AsyncSessionLocal
from sqlalchemy import text

async def create_important_events_table():
    """
    Create important_events table to store customer important events.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Check if table already exists
            result = await db.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'important_events'
            """))

            if result.fetchone():
                print("Table 'important_events' already exists")
                return

            # Create the table
            await db.execute(text("""
                CREATE TABLE important_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    title VARCHAR(255) NOT NULL,
                    event_date TIMESTAMP NOT NULL,
                    recurring BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Create indexes
            await db.execute(text("""
                CREATE INDEX idx_important_event_user ON important_events(user_id, event_date)
            """))

            await db.execute(text("""
                CREATE INDEX idx_important_event_date ON important_events(event_date)
            """))

            await db.commit()
            print("Successfully created 'important_events' table")

        except Exception as e:
            print(f"Error creating table: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_important_events_table())