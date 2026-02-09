import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal
from models import Order, Invoice
from sqlalchemy import select, exists

async def check_orders():
    async with AsyncSessionLocal() as db:
        try:
            # Count total orders
            result = await db.execute(select(Order.id))
            total_orders = len(result.scalars().all())
            print(f"Total orders: {total_orders}")

            # Count orders with invoices
            result = await db.execute(
                select(Order.id).where(
                    exists().where(Invoice.order_id == Order.id)
                )
            )
            orders_with_invoices = len(result.scalars().all())
            print(f"Orders with invoices: {orders_with_invoices}")

            # Count orders without invoices
            orders_without_invoices = total_orders - orders_with_invoices
            print(f"Orders without invoices: {orders_without_invoices}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_orders())