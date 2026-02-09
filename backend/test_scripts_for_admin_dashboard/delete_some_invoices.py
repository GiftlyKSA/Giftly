import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal
from models import Invoice
from sqlalchemy import select, delete

async def delete_some_invoices():
    async with AsyncSessionLocal() as db:
        try:
            # Delete the first 3 invoices to create orders without invoices
            result = await db.execute(select(Invoice.id).limit(3))
            invoice_ids = [row[0] for row in result.fetchall()]

            if invoice_ids:
                result = await db.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))
                invoices_deleted = result.rowcount
                print(f"Deleted {invoices_deleted} invoices")

                await db.commit()
                print("Some invoices deleted successfully. Now there are orders without invoices.")
            else:
                print("No invoices found to delete.")

        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(delete_some_invoices())