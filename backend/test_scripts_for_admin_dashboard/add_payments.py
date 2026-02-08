import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import User, Invoice, Payment, PaymentMethod, PaymentStatus
from datetime import datetime
from sqlalchemy import select

async def add_payments():
    async with AsyncSessionLocal() as db:
        try:
            # Get all invoices that don't have payments yet
            result = await db.execute(
                select(Invoice).where(
                    ~Invoice.id.in_(
                        select(Payment.invoice_id).where(Payment.status == PaymentStatus.COMPLETED)
                    )
                )
            )
            invoices = result.scalars().all()

            if not invoices:
                print("No unpaid invoices found. Please create orders and invoices first.")
                return

            payments_created = 0
            for invoice in invoices:
                # Get the user for this invoice (through the order)
                result = await db.execute(select(User).where(User.id == invoice.order.created_by_user_id))
                user = result.scalar_one_or_none()
                if not user:
                    print(f"User not found for invoice {invoice.invoice_id}")
                    continue

                # Create a payment for this invoice
                payment_method = PaymentMethod.WALLET if user.role == 'Customer' else PaymentMethod.CREDIT_CARD

                payment = Payment(
                    invoice_id=invoice.id,
                    user_id=user.id,
                    amount=invoice.full_amount,
                    payment_method=payment_method,
                    status=PaymentStatus.COMPLETED,
                    transaction_id=f"TXN-{invoice.invoice_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    payment_date=datetime.now(),
                    payment_details=f"Payment for invoice {invoice.invoice_id}"
                )
                db.add(payment)
                print(f"Created payment for invoice {invoice.invoice_id} - {invoice.full_amount} halaym via {payment_method.value}")
                payments_created += 1

            await db.commit()
            print(f"All payments created successfully. Total payments: {payments_created}")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(add_payments())