from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import select
from database import get_db
from models import Payment, Invoice, User, Wallet, OrderStatus, InvoiceStatus, PaymentStatus
from schemas import PaymentResponse, CreatePayment
from auth import get_current_user
from typing import List
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=PaymentResponse)
async def create_payment(payment_data: CreatePayment, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Create a new payment for an invoice. User must own the invoice.
    """
    # Check if invoice exists and user owns it
    result = await db.execute(select(Invoice).where(Invoice.id == payment_data.invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=400, detail="Invoice not found")

    # Check if user owns this invoice (through order)
    result = await db.execute(
        select(Invoice).join(Invoice.order).where(
            Invoice.id == payment_data.invoice_id,
            Invoice.order.has(Order.created_by_user_id == current_user.id)
        )
    )
    order_check = result.scalar_one_or_none()
    if not order_check:
        raise HTTPException(status_code=403, detail="Access denied - invoice not owned by user")

    # Check if user exists (should be current user)
    if payment_data.user_id != current_user.id:
        raise HTTPException(status_code=400, detail="User ID must match current user")

    # Create the payment
    new_payment = Payment(
        invoice_id=payment_data.invoice_id,
        user_id=payment_data.user_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        status=PaymentStatus.COMPLETED,
        transaction_id=payment_data.transaction_id,
        payment_details=payment_data.payment_details
    )

    db.add(new_payment)
    await db.commit()
    await db.refresh(new_payment)

    # Check if invoice is fully paid
    result = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.invoice_id == payment_data.invoice_id,
            Payment.status == PaymentStatus.COMPLETED
        )
    )
    total_paid = result.scalar() or 0
    if total_paid >= invoice.full_amount:
        invoice.status = InvoiceStatus.PAID
        invoice.updated_at = datetime.utcnow()
        invoice.order.status = OrderStatus.PAID
        invoice.order.updated_at = datetime.utcnow()
        await db.commit()

        # Send chat message about successful payment
        if invoice.order.conversation:
            from websocket_events import emit_chat_message
            from models import Message

            payment_message_content = f"تم دفع الفاتورة بنجاح - المبلغ المدفوع: {total_paid:.2f} ريال"

            payment_message = Message(
                conversation_id=invoice.order.conversation.id,
                sender_id=current_user.id,  # Customer who paid
                content=payment_message_content,
                message_type='text'
            )
            db.add(payment_message)
            await db.commit()
            await db.refresh(payment_message)

            # Emit the payment message via WebSocket
            await emit_chat_message(invoice.order.conversation.id, {
                "id": payment_message.id,
                "conversation_id": payment_message.conversation_id,
                "sender_id": payment_message.sender_id,
                "content": payment_message.content,
                "message_type": payment_message.message_type,
                "sent_at": payment_message.sent_at.isoformat()
            }, db)

        # Emit order status change event
        from websocket_events import emit_order_status_change
        await emit_order_status_change(invoice.order.id, invoice.order.status.value)

    return new_payment

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get payment by ID. User can only view their own payments.
    """
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Check if user owns this payment
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return payment

@router.get("/invoice/{invoice_id}", response_model=List[PaymentResponse])
async def get_payments_by_invoice(invoice_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get all payments for an invoice. User can only view payments for their own invoices.
    """
    # Check if invoice exists and user owns it
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if user owns this invoice (through order)
    result = await db.execute(
        select(Invoice).join(Invoice.order).where(
            Invoice.id == invoice_id,
            Invoice.order.has(Order.created_by_user_id == current_user.id)
        )
    )
    order_check = result.scalar_one_or_none()
    if not order_check:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(Payment).where(Payment.invoice_id == invoice_id))
    payments = result.scalars().all()
    return payments

@router.get("/my-payments", response_model=List[PaymentResponse])
async def get_my_payments(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get all payments by current user.
    """
    result = await db.execute(select(Payment).where(Payment.user_id == current_user.id))
    payments = result.scalars().all()
    return payments

@router.post("/pay-with-wallet/{invoice_id}")
async def pay_with_wallet(
    invoice_id: int,
    coupon_code: str = None,
    background_tasks: BackgroundTasks = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pay for an invoice using wallet balance. Optional coupon support.
    """
    # Check if invoice exists and user owns it
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if user owns this invoice (through order)
    if invoice.order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if invoice is already paid
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    # Get user's wallet
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found. Please create a wallet first.")

    # Calculate final payment amount (with coupon if provided)
    payment_amount = invoice.full_amount
    coupon_used = None

    if coupon_code:
        # Import Promocode for coupon verification
        from models import Promocode

        # Find the coupon
        result = await db.execute(select(Promocode).where(Promocode.code == coupon_code.upper()))
        coupon = result.scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=400, detail="Invalid coupon code")

        # Check if coupon is active and not expired
        if not coupon.active or coupon.valid_until < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Coupon is expired or inactive")

        # Check usage limit
        if coupon.usage_count >= coupon.usage_limit and coupon.usage_limit > 0:
            raise HTTPException(status_code=400, detail="Coupon usage limit exceeded")

        # Check minimum order value
        if invoice.full_amount < coupon.minimum_order_value:
            raise HTTPException(status_code=400, detail=f"Minimum order value for this coupon is {coupon.minimum_order_value}")

        # Calculate discount
        discount_amount = 0
        if coupon.applicable_to == "order_total":
            if coupon.percentage > 0:
                discount_amount = invoice.full_amount * (coupon.percentage / 100)
            if coupon.max_value > 0 and discount_amount > coupon.max_value:
                discount_amount = coupon.max_value
        elif coupon.applicable_to == "service_fee":
            if coupon.percentage > 0:
                discount_amount = invoice.service_fee * (coupon.percentage / 100)
            if coupon.max_value > 0 and discount_amount > coupon.max_value:
                discount_amount = coupon.max_value
        elif coupon.applicable_to == "delivery_fee":
            if coupon.percentage > 0:
                discount_amount = invoice.courier_fee * (coupon.percentage / 100)
            if coupon.max_value > 0 and discount_amount > coupon.max_value:
                discount_amount = coupon.max_value

        payment_amount = invoice.full_amount - discount_amount
        if payment_amount < 0:
            payment_amount = 0

        coupon_used = coupon

    # Check if wallet has sufficient balance for the final amount
    if wallet.balance < payment_amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    try:
        # Record balance before payment
        balance_before = wallet.balance

        # Deduct amount from wallet
        wallet.balance -= payment_amount
        wallet.updated_at = datetime.utcnow()

        # Mark invoice as paid
        from models import InvoiceStatus, PaymentStatus, PaymentMethod
        invoice.status = InvoiceStatus.PAID
        invoice.updated_at = datetime.utcnow()

        # Store coupon used if applicable
        if coupon_used:
            invoice.promocode_id = coupon_used.id
            coupon_used.usage_count += 1
            coupon_used.updated_at = datetime.utcnow()

        # Mark order as paid
        invoice.order.status = OrderStatus.PAID
        invoice.order.updated_at = datetime.utcnow()

        # Create payment record with the discounted amount
        payment = Payment(
            invoice_id=invoice_id,
            user_id=current_user.id,
            amount=payment_amount,  # Use the discounted amount
            payment_method=PaymentMethod.WALLET,
            status=PaymentStatus.COMPLETED,
            payment_date=datetime.utcnow(),
            wallet_balance_before=balance_before
        )

        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        # Send chat message about successful payment
        if invoice.order.conversation:
            from websocket_events import emit_chat_message
            from models import Message

            payment_message_content = f"تم دفع الفاتورة بنجاح - المبلغ المدفوع: {payment_amount:.2f} ريال"
            if coupon_used:
                payment_message_content += f"\n(تم تطبيق خصم: {discount_amount:.2f} ريال)"

            payment_message = Message(
                conversation_id=invoice.order.conversation.id,
                sender_id=current_user.id,  # Customer who paid
                content=payment_message_content,
                message_type='text'
            )
            db.add(payment_message)
            await db.commit()
            await db.refresh(payment_message)

            # Emit the payment message via WebSocket
            await emit_chat_message(invoice.order.conversation.id, {
                "id": payment_message.id,
                "conversation_id": payment_message.conversation_id,
                "sender_id": payment_message.sender_id,
                "content": payment_message.content,
                "message_type": payment_message.message_type,
                "sent_at": payment_message.sent_at.isoformat()
            }, db)

        # Emit order status change event
        from websocket_events import emit_order_status_change
        await emit_order_status_change(invoice.order.id, invoice.order.status.value)

        # Send invoice email in background (now that payment is successful)
        if background_tasks:
            from utils.background_email import send_invoice_email_background
            background_tasks.add_task(send_invoice_email_background, invoice.id, db)

        return {
            "message": f"Payment successful{f'. Discount applied: {discount_amount:.2f} SAR' if coupon_used else ''}",
            "payment_id": payment.id,
            "remaining_balance": wallet.balance,
            "final_amount": payment_amount,
            "discount_amount": discount_amount if coupon_used else 0
        }

    except Exception as e:
        await db.rollback()
        print(f"Error processing wallet payment: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing payment. Please try again.")
