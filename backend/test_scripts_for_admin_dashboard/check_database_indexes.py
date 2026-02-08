import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import engine
from sqlalchemy import text

async def check_database_indexes():
    """
    Check if all database indexes exist and are properly created.
    This script verifies that the indexing script worked correctly.
    """
    expected_indexes = {
        'users': [
            'idx_user_role',
            'idx_user_city',
            'idx_user_admin'
        ],
        'orders': [
            'idx_order_created_by',
            'idx_order_assigned_to',
            'idx_order_status',
            'idx_order_city',
            'idx_order_delivery',
            'idx_order_admin'
        ],
        'invoices': [
            'idx_invoice_order',
            'idx_invoice_status',
            'idx_invoice_paid'
        ],
        'jwt_tokens': [
            'idx_jwt_user',
            'idx_jwt_expiry'
        ],
        'conversations': [
            'idx_conversation_customer',
            'idx_conversation_courier',
            'idx_conversation_status'
        ],  # Note: uses 'created_at' not 'updated_at'
        'messages': [
            'idx_message_conversation',
            'idx_message_sender',
            'idx_message_type'
        ]
    }

    try:
        print("🔍 Checking database indexes...\n")

        all_good = True

        async with engine.begin() as conn:
            for table, indexes in expected_indexes.items():
                print(f"📋 Checking table: {table}")

                # Get existing indexes for this table
                result = await conn.execute(text("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = :table_name
                    ORDER BY indexname
                """), {"table_name": table})

                existing_indexes = [row[0] for row in result.fetchall()]
                print(f"   Found indexes: {', '.join(existing_indexes) if existing_indexes else 'None'}")

                # Check each expected index
                for expected_index in indexes:
                    if expected_index in existing_indexes:
                        print(f"   ✅ {expected_index} - EXISTS")
                    else:
                        print(f"   ❌ {expected_index} - MISSING")
                        all_good = False

                print()

        if all_good:
            print("🎉 All database indexes are properly created!")
            print("\n📊 Your database is optimized for:")
            print("  • Fast OTP operations")
            print("  • Quick order queries")
            print("  • Efficient chat loading")
            print("  • Smooth admin dashboard")
        else:
            print("⚠️  Some indexes are missing. Run the add_database_indexes.py script to create them.")

        # Additional check: Show index sizes
        print("\n📏 Index Sizes:")
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 10
            """))

            index_sizes = result.fetchall()
            if index_sizes:
                for row in index_sizes:
                    print(f"  {row[2]} ({row[1]}): {row[3]}")
            else:
                print("  No indexes found or size data unavailable.")

    except Exception as e:
        print(f"❌ Error checking indexes: {e}")
        print("Make sure your database is running and accessible.")

if __name__ == "__main__":
    asyncio.run(check_database_indexes())