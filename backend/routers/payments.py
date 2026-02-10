from fastapi import APIRouter, Depends, HTTPException, status
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
async def pay_with_wallet(invoice_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Pay for an invoice using wallet balance.
    """
    # Check if invoice exists and user owns it
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="'DA'*H1) :J1 EH,H/)")

    # Check if user owns this invoice (through order)
    if invoice.order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="DJ3 D/JC 5D'-J) 'DH5HD DG0G 'DA'*H1)")

    # Check if invoice is already paid
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="'DA'*H1) E/AH9) ('DA9D")

    # Get user's wallet
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="'لا يوجد لديك محفظة. يرجى إنشاء محفظة أولاً.")

    # Check if wallet has sufficient balance
    if wallet.balance < invoice.full_amount:
        raise HTTPException(status_code=400, detail="رصيد المحفظة غير كافٍ.")

    try:
        # Record balance before payment
        balance_before = wallet.balance

        # Deduct amount from wallet
        wallet.balance -= invoice.full_amount
        wallet.updated_at = datetime.utcnow()

        # Mark invoice as paid
        from models import InvoiceStatus, PaymentStatus, PaymentMethod
        invoice.status = InvoiceStatus.PAID
        invoice.updated_at = datetime.utcnow()

        # Mark order as paid
        invoice.order.status = OrderStatus.PAID
        invoice.order.updated_at = datetime.utcnow()

        # Create payment record
        payment = Payment(
            invoice_id=invoice_id,
            user_id=current_user.id,
            amount=invoice.full_amount,
            payment_method=PaymentMethod.WALLET,
            status=PaymentStatus.COMPLETED,
            payment_date=datetime.utcnow(),
            wallet_balance_before=balance_before
        )

        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        return {
            "message": "تمت عملية الدفع بنجاح",
            "payment_id": payment.id,
            "remaining_balance": wallet.balance
        }

    except Exception as e:
        await db.rollback()
        print(f"Error processing wallet payment: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء معالجة الدفع. يرجى المحاولة مرة أخرى.")
