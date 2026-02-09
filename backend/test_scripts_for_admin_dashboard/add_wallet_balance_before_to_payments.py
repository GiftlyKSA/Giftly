import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import get_db_sync
from sqlalchemy import text

def add_wallet_balance_before_column():
    """
    Add wallet_balance_before column to payments table.
    This column stores the wallet balance before a wallet payment was made.
    """
    db_gen = get_db_sync()
    db = next(db_gen)
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'payments' AND column_name = 'wallet_balance_before'
        """))

        if result.fetchone():
            print("Column 'wallet_balance_before' already exists in payments table")
            return

        # Add the column
        db.execute(text("""
            ALTER TABLE payments
            ADD COLUMN wallet_balance_before INTEGER
        """))

        db.commit()
        print("Successfully added 'wallet_balance_before' column to payments table")

    except Exception as e:
        print(f"Error adding column: {e}")
        db.rollback()
    finally:
        try:
            next(db_gen)  # Close the session
        except StopIteration:
            pass

if __name__ == "__main__":
    add_wallet_balance_before_column()
