import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def add_revoked_tokens_table():
    """
    Create database table for revoked tokens.
    This script creates the revoked_tokens table and its indexes for JWT token revocation.
    """
    try:
        print("Starting creation of revoked_tokens table...")

        async with engine.begin() as conn:
            # Create revoked_tokens table
            print("Creating revoked_tokens table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    id SERIAL PRIMARY KEY,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    expires_at TIMESTAMP NOT NULL,
                    revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Create indexes for revoked_tokens table
            print("Creating revoked_tokens indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_revoked_token_hash ON revoked_tokens(token_hash);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_revoked_user ON revoked_tokens(user_id, revoked_at);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_revoked_expiry ON revoked_tokens(expires_at);"))

        print("\n🎉 Revoked tokens table created successfully!")
        print("\n📊 New table added:")
        print("  • revoked_tokens - JWT token revocation storage")

    except Exception as e:
        print(f"❌ Error creating table: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(add_revoked_tokens_table())