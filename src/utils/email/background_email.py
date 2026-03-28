from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import User, Invoice, Order
from .email_utils import send_email_with_template
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def send_welcome_email_background(user_id: int, db: AsyncSession):
    """
    Background task to send welcome email to newly registered user.
    """
    try:
        # Get user details
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.email:
            logger.warning(f"User {user_id} not found or has no email")
            return

        # Send welcome email
        success = send_email_with_template(
            to_email=user.email,
            subject="مرحباً بك في هديتي",
            template_name="welcome_email",
            template_vars={
                "user_name": user.name or user.phone_number,
                "app_url": "https://giftly.com/app"  # Replace with actual app URL
            }
        )

        if success:
            logger.info(f"Welcome email sent successfully to user {user_id}")
        else:
            logger.error(f"Failed to send welcome email to user {user_id}")

    except Exception as e:
        logger.error(f"Error sending welcome email to user {user_id}: {str(e)}")

async def send_invoice_email_background(invoice_id: int, db: AsyncSession):
    """
    Background task to send invoice email to customer and mark as sent.
    """
    try:
        # Get invoice with order and user details
        result = await db.execute(
            select(Invoice)
            .join(Order, Invoice.order_id == Order.id)
            .join(User, Order.created_by_user_id == User.id)
            .where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if not invoice or not invoice.order or not invoice.order.created_by_user or not invoice.order.created_by_user.email:
            logger.warning(f"Invoice {invoice_id} not found or customer has no email")
            return

        customer = invoice.order.created_by_user

        # Prepare invoice data for template
        is_paid = invoice.status.value == "paid"
        template_vars = {
            "customer_name": customer.name or customer.phone_number,
            "order_id": invoice.order.order_id,
            "invoice_id": invoice.invoice_id,
            "delivery_date": invoice.order.delivery_date.strftime("%Y-%m-%d") if invoice.order.delivery_date else "غير محدد",
            "status_text": "مدفوعة" if is_paid else "في انتظار الدفع",
            "status_class": "paid" if is_paid else "pending",
            "gift_price": f"{invoice.order_only_price / 100:.2f}",  # Convert from cents to riyals
            "service_fee": f"{invoice.service_fee / 100:.2f}",
            "delivery_fee": f"{invoice.courier_fee / 100:.2f}",
            "discount_amount": f"{invoice.discount_amount / 100:.2f}" if invoice.discount_amount else "0.00",
            "tax_amount": f"{invoice.tax_amount / 100:.2f}",
            "total_amount": f"{invoice.full_amount / 100:.2f}",
            "payment_url": "" if is_paid else f"https://giftly.com/pay/{invoice.invoice_id}",  # No payment URL for paid invoices
            "due_date": None if is_paid else (invoice.due_date.strftime("%Y-%m-%d") if invoice.due_date else None),
            "notes": "تم دفع الفاتورة بنجاح. شكراً لاستخدام خدماتنا!" if is_paid else (invoice.comment or "")
        }

        # Send invoice email
        success = send_email_with_template(
            to_email=customer.email,
            subject=f"فاتورة طلبك من هديتي - {invoice.invoice_id}",
            template_name="invoice_email",
            template_vars=template_vars
        )

        if success:
            # Mark invoice as sent via email
            await db.execute(
                update(Invoice)
                .where(Invoice.id == invoice_id)
                .values(
                    sent_to_user_via_email=True,
                    sent_at=datetime.utcnow()
                )
            )
            await db.commit()
            logger.info(f"Invoice email sent successfully for invoice {invoice_id}")
        else:
            logger.error(f"Failed to send invoice email for invoice {invoice_id}")

    except Exception as e:
        logger.error(f"Error sending invoice email for invoice {invoice_id}: {str(e)}")

async def send_payment_confirmation_email_background(invoice_id: int, db: AsyncSession):
    """
    Background task to send payment confirmation email to customer.
    """
    try:
        # Get invoice with order and user details
        result = await db.execute(
            select(Invoice)
            .join(Order, Invoice.order_id == Order.id)
            .join(User, Order.created_by_user_id == User.id)
            .where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if not invoice or not invoice.order or not invoice.order.created_by_user or not invoice.order.created_by_user.email:
            logger.warning(f"Invoice {invoice_id} not found or customer has no email")
            return

        customer = invoice.order.created_by_user

        # Send payment confirmation email (using invoice template with paid status)
        template_vars = {
            "customer_name": customer.name or customer.phone_number,
            "order_id": invoice.order.order_id,
            "invoice_id": invoice.invoice_id,
            "delivery_date": invoice.order.delivery_date.strftime("%Y-%m-%d") if invoice.order.delivery_date else "غير محدد",
            "status_text": "مدفوعة",
            "status_class": "paid",
            "gift_price": f"{invoice.order_only_price / 100:.2f}",
            "service_fee": f"{invoice.service_fee / 100:.2f}",
            "delivery_fee": f"{invoice.courier_fee / 100:.2f}",
            "discount_amount": invoice.discount_amount / 100 if invoice.discount_amount else 0,
            "tax_amount": f"{invoice.tax_amount / 100:.2f}",
            "total_amount": f"{invoice.full_amount / 100:.2f}",
            "payment_url": "",  # No payment URL for paid invoices
            "due_date": None,
            "notes": "تم دفع الفاتورة بنجاح. شكراً لاستخدام خدماتنا!"
        }

        success = send_email_with_template(
            to_email=customer.email,
            subject=f"تأكيد دفع الفاتورة - {invoice.invoice_id}",
            template_name="invoice_email",
            template_vars=template_vars
        )

        if success:
            logger.info(f"Payment confirmation email sent successfully for invoice {invoice_id}")
        else:
            logger.error(f"Failed to send payment confirmation email for invoice {invoice_id}")

    except Exception as e:
        logger.error(f"Error sending payment confirmation email for invoice {invoice_id}: {str(e)}")