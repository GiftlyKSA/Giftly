import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal
from models import Order, Invoice, InvoiceStatus
from sqlalchemy import select, exists
from sqlalchemy.orm import selectinload

async def create_invoices_for_orders():
    """
    Create invoices for all orders that don't have invoices yet.
    The user who creates the invoices is user ID 5.
    """
    async with AsyncSessionLocal() as db:
        try:
            print("Starting to create invoices for orders without invoices...")

            # Find all orders that don't have invoices
            # Using a subquery to check for existence of invoice
            orders_without_invoices = await db.execute(
                select(Order).where(
                    ~exists().where(Invoice.order_id == Order.id)
                ).options(selectinload(Order.created_by_user))
            )
            orders = orders_without_invoices.scalars().all()

            if not orders:
                print("No orders found that need invoices.")
                return

            print(f"Found {len(orders)} orders without invoices.")

            created_count = 0
            for order in orders:
                # Calculate invoice amounts (similar to existing logic)
                # For simplicity, using basic calculation - you may need to adjust based on business logic
                order_only_price = 200  # Default value - adjust as needed
                courier_fee = 50
                tax_amount = int(order_only_price * 0.15)  # 15% tax
                service_fee = int((order_only_price + courier_fee + tax_amount) * 0.20)  # 20% service fee
                full_amount = order_only_price + courier_fee + tax_amount + service_fee

                # Generate unique invoice ID
                invoice_count = await db.execute(select(Invoice).with_only_columns(Invoice.id))
                invoice_id = f"INV-{len(invoice_count.scalars().all()) + 1:06d}"

                # Create invoice
                invoice = Invoice(
                    invoice_id=invoice_id,
                    order_id=order.id,
                    created_by_user_id=5,  # User ID 5 creates the invoice
                    full_amount=full_amount,
                    service_fee=service_fee,
                    order_only_price=order_only_price,
                    courier_fee=courier_fee,
                    tax_amount=tax_amount,
                    status=InvoiceStatus.NEW,
                    description=f"Invoice for order {order.order_id}"
                )

                db.add(invoice)
                created_count += 1
                print(f"Created invoice {invoice_id} for order {order.order_id}")

            await db.commit()
            print(f"Successfully created {created_count} invoices.")

        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_invoices_for_orders())