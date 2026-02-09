from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from database import get_db_sync
from models import Payment, Invoice, User, Wallet, OrderStatus, InvoiceStatus, PaymentStatus
from schemas import PaymentResponse, CreatePayment
from auth import get_current_user
from typing import List
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=PaymentResponse)
def create_payment(payment_data: CreatePayment, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Create a new payment for an invoice. User must own the invoice.
    """
    # Check if invoice exists and user owns it
    invoice = db.query(Invoice).filter(Invoice.id == payment_data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=400, detail="Invoice not found")

    # Check if user owns this invoice (through order)
    order = db.query(Invoice).join(Invoice.order).filter(Invoice.id == payment_data.invoice_id).first()
    if not order or order.order.created_by_user_id != current_user.id:
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
    db.commit()
    db.refresh(new_payment)

    # Check if invoice is fully paid
    total_paid = db.query(func.sum(Payment.amount)).filter(Payment.invoice_id == payment_data.invoice_id, Payment.status == PaymentStatus.COMPLETED).scalar() or 0
    if total_paid >= invoice.full_amount:
        invoice.status = InvoiceStatus.PAID
        invoice.updated_at = datetime.utcnow()
        invoice.order.status = OrderStatus.PAID
        invoice.order.updated_at = datetime.utcnow()
        db.commit()

    return new_payment

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Get payment by ID. User can only view their own payments.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Check if user owns this payment
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return payment

@router.get("/invoice/{invoice_id}", response_model=List[PaymentResponse])
def get_payments_by_invoice(invoice_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Get all payments for an invoice. User can only view payments for their own invoices.
    """
    # Check if invoice exists and user owns it
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if user owns this invoice (through order)
    order = db.query(Invoice).join(Invoice.order).filter(Invoice.id == invoice_id).first()
    if not order or order.order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    payments = db.query(Payment).filter(Payment.invoice_id == invoice_id).all()
    return payments

@router.get("/my-payments", response_model=List[PaymentResponse])
def get_my_payments(current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Get all payments by current user.
    """
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).all()
    return payments

@router.post("/pay-with-wallet/{invoice_id}")
def pay_with_wallet(invoice_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Pay for an invoice using wallet balance.
    """
    # Check if invoice exists and user owns it
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="'DA'*H1) :J1 EH,H/)")

    # Check if user owns this invoice (through order)
    if invoice.order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="DJ3 D/JC 5D'-J) 'DH5HD DG0G 'DA'*H1)")

    # Check if invoice is already paid
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="'DA'*H1) E/AH9) ('DA9D")

    # Get user's wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
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
        db.commit()
        db.refresh(payment)

        return {
            "message": "تمت عملية الدفع بنجاح",
            "payment_id": payment.id,
            "remaining_balance": wallet.balance
        }

    except Exception as e:
        db.rollback()
        print(f"Error processing wallet payment: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء معالجة الدفع. يرجى المحاولة مرة أخرى.")
