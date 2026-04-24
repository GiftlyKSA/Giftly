import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func

from models import (
    Invoice,
    InvoiceStatus,
    Order,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Promocode,
    PromocodeUsage,
    User,
    Wallet,
)
from models.enums import PaymentMethod as PaymentMethodEnum
from schemas import CreatePayment, PaymentResponse
from utils.auth.auth import get_current_user
from utils.database.config import settings
from utils.database.database import get_db
from utils.rate_limit import make_ip_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Rate limiters — values come from settings (configurable via .env)
# ---------------------------------------------------------------------------

_callback_timestamps: dict[str, list[float]] = defaultdict(list)
_payment_rate_limit = make_ip_rate_limiter(
    settings.rate_limit_payment_create_per_minute, 60
)


def _check_callback_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    window = 60.0
    valid = [t for t in _callback_timestamps[client_ip] if now - t < window]
    _callback_timestamps[client_ip] = valid
    if len(valid) >= settings.paylink_callback_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Too many requests")
    _callback_timestamps[client_ip] = valid + [now]


# ---------------------------------------------------------------------------
# Pydantic schema for Paylink webhook payload
# ---------------------------------------------------------------------------

class PaylinkCallbackPayload(BaseModel):
    transactionNo: Optional[str] = None
    orderNumber: Optional[str] = None
    orderStatus: Optional[str] = None
    status: Optional[str] = None

    model_config = {"extra": "allow"}  # Paylink may add extra fields

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mark_invoice_paid(
    invoice: Invoice, total_paid: int, current_user: User, db: AsyncSession
):
    """Set invoice + order to PAID, send payment chat message, emit WS events."""
    invoice.status = InvoiceStatus.PAID
    invoice.updated_at = datetime.now(timezone.utc)
    invoice.order.status = OrderStatus.PAID
    invoice.order.updated_at = datetime.now(timezone.utc)
    await db.commit()

    if invoice.order.conversation:
        from models import Message
        from utils.websocket.websocket_events import emit_chat_message

        msg = Message(
            conversation_id=invoice.order.conversation.id,
            sender_id=current_user.id,
            content=f"تم دفع الفاتورة بنجاح - المبلغ المدفوع: {total_paid / 100:.2f} ريال",
            message_type="text",
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        await emit_chat_message(
            invoice.order.conversation.id,
            {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "message_type": msg.message_type,
                "sent_at": msg.sent_at.isoformat(),
            },
            db,
        )

        from utils.websocket.websocket_events import emit_order_status_change

        await emit_order_status_change(invoice.order.id, invoice.order.status.value)


# ---------------------------------------------------------------------------
# Paylink-gated payment methods
# ---------------------------------------------------------------------------

PAYLINK_METHODS = {
    PaymentMethodEnum.CREDIT_CARD,
    PaymentMethodEnum.APPLE_PAY,
    PaymentMethodEnum.MADA,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=PaymentResponse)
async def create_payment(
    payment_data: CreatePayment,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_payment_rate_limit),
):
    """
    Create a payment record.
    For CREDIT_CARD / APPLE_PAY / MADA: initiates Paylink and returns a payment URL.
    For WALLET: use /pay-with-wallet instead.
    """
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.order).selectinload(Order.conversation))
        .where(Invoice.id == payment_data.invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.order.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Access denied — invoice not owned by user"
        )

    if payment_data.user_id != current_user.id:
        raise HTTPException(status_code=400, detail="User ID must match current user")

    # --- Paylink gateway for card-based methods ---
    from utils.database.config import settings

    if payment_data.payment_method in PAYLINK_METHODS:
        if not settings.paylink_api_key:
            raise HTTPException(
                status_code=503,
                detail="Payment gateway not configured. Contact support.",
            )

        new_payment = Payment(
            invoice_id=payment_data.invoice_id,
            user_id=current_user.id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            status=PaymentStatus.PENDING,
        )
        db.add(new_payment)
        await db.commit()
        await db.refresh(new_payment)

        from utils.clients.paylink import PaylinkClient

        try:
            async with PaylinkClient(
                settings.paylink_api_key,
                settings.paylink_test_mode,
                api_id=settings.paylink_api_id,
            ) as paylink:
                resp = await paylink.create_invoice(
                    {
                        "amount": round(payment_data.amount / 100, 2),
                        "currency": "SAR",
                        "description": f"Invoice {invoice.invoice_id}",
                        "customer": {
                            "name": current_user.name or "Customer",
                            "email": current_user.email or "",
                            "phone": current_user.phone_number,
                        },
                        "invoiceNumber": str(new_payment.id),
                        "callBackUrl": settings.paylink_callback_url,
                        "returnUrl": settings.paylink_return_url,
                    }
                )
        except Exception as e:
            logging.error("Paylink create_order failed: %s", str(e))
            new_payment.status = PaymentStatus.FAILED
            await db.commit()
            raise HTTPException(status_code=502, detail="Something went wrong. Please contact administration.")

        new_payment.transaction_id = str(
            resp.get("transactionNo") or resp.get("id") or ""
        )
        await db.commit()
        await db.refresh(new_payment)

        # Return payment_url alongside the standard PaymentResponse fields
        return new_payment  # client should also check payment_url in response body via dict

    # --- Wallet: redirect to the proper endpoint ---
    if payment_data.payment_method == PaymentMethodEnum.WALLET:
        raise HTTPException(
            status_code=400,
            detail="Use POST /payments/pay-with-wallet/{invoice_id} for wallet payments.",
        )

    raise HTTPException(status_code=400, detail="Unsupported payment method")


@router.post("/paylink-callback")
async def paylink_callback(
    payload: PaylinkCallbackPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint called by Paylink after a payment completes.
    Verifies the transaction and marks the payment/invoice as paid.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_callback_rate_limit(client_ip)

    # M-01: In production, refuse unsigned webhooks entirely
    if not settings.paylink_webhook_secret and not settings.debug:
        raise HTTPException(
            status_code=503,
            detail="Webhook endpoint not configured. Contact support.",
        )

    # HMAC signature verification — enforced when PAYLINK_WEBHOOK_SECRET is set
    if settings.paylink_webhook_secret:
        raw_body = await request.body()
        expected_sig = hmac.new(
            settings.paylink_webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        received_sig = request.headers.get("x-paylink-signature", "")
        if not hmac.compare_digest(expected_sig, received_sig):
            logger.warning(
                "paylink_callback signature mismatch from=%s transaction=%s",
                client_ip,
                payload.transactionNo or payload.orderNumber,
            )
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    transaction_no = str(payload.transactionNo or payload.orderNumber or "")
    paylink_status = str(payload.orderStatus or payload.status or "").lower()

    logger.info(
        "paylink_callback from=%s transaction=%s status=%s",
        client_ip, transaction_no, paylink_status,
    )

    if not transaction_no:
        logger.warning("paylink_callback received with no transaction number from=%s", client_ip)
        raise HTTPException(status_code=400, detail="Missing transaction number")

    # Find the pending payment by transaction_id OR by id (wallet top-up uses payment.id as orderNumber)
    result = await db.execute(
        select(Payment)
        .options(
            selectinload(Payment.invoice)
            .selectinload(Invoice.order)
            .selectinload(Order.conversation),
            selectinload(Payment.user),
        )
        .where(Payment.transaction_id == transaction_no)
    )
    payment = result.scalar_one_or_none()

    # Fallback: try by payment.id (wallet top-up flow)
    if not payment:
        try:
            pid = int(transaction_no)
            result = await db.execute(
                select(Payment)
                .options(
                    selectinload(Payment.invoice)
                    .selectinload(Invoice.order)
                    .selectinload(Order.conversation),
                    selectinload(Payment.user),
                )
                .where(
                    Payment.id == pid, Payment.status == PaymentStatus.PENDING
                )
            )
            payment = result.scalar_one_or_none()
        except ValueError:
            pass

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Re-validate status with Paylink API to prevent spoofed webhooks
    if settings.paylink_api_key and not settings.paylink_test_mode:
        try:
            from utils.clients.paylink import PaylinkClient
            async with PaylinkClient(
                settings.paylink_api_key,
                test_mode=settings.paylink_test_mode,
                api_id=settings.paylink_api_id,
            ) as paylink:
                live = await paylink.get_invoice(transaction_no)
                live_status = str(live.get("orderStatus") or live.get("status") or "").lower()
                if live_status != paylink_status:
                    logging.warning(
                        "paylink_callback status mismatch: webhook=%s live=%s transaction=%s",
                        paylink_status, live_status, transaction_no,
                    )
                    paylink_status = live_status
        except Exception as e:
            logging.error("Paylink re-validation failed for %s: %s", transaction_no, str(e))

    if paylink_status in ("paid", "completed", "success"):
        # Atomic update prevents double-credit when Paylink retries the webhook concurrently
        atomic = await db.execute(
            update(Payment)
            .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING)
            .values(status=PaymentStatus.COMPLETED, payment_date=datetime.now(timezone.utc))
        )
        if atomic.rowcount == 0:
            return {"message": "Already processed"}
        await db.commit()

        # Invoice payment: mark invoice + order paid
        # invoice and user are already loaded via selectinload on the initial query
        # (expire_on_commit=False means they survive the commit above)
        if payment.invoice_id:
            invoice = payment.invoice
            payer = payment.user
            if invoice and payer:
                try:
                    result4 = await db.execute(
                        select(func.sum(Payment.amount)).where(
                            Payment.invoice_id == invoice.id,
                            Payment.status == PaymentStatus.COMPLETED,
                        )
                    )
                    total_paid = result4.scalar() or 0
                    if total_paid >= invoice.full_amount:
                        await _mark_invoice_paid(invoice, total_paid, payer, db)
                except Exception:
                    logger.exception(
                        "paylink_callback: invoice processing failed "
                        "payment=%s invoice=%s transaction=%s",
                        payment.id, invoice.id, transaction_no,
                    )
                    raise

        # Wallet top-up: credit atomically to prevent double-credit race condition
        else:
            await db.execute(
                update(Wallet)
                .where(Wallet.user_id == payment.user_id)
                .values(
                    balance=Wallet.balance + payment.amount,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

    else:
        failed = await db.execute(
            update(Payment)
            .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING)
            .values(status=PaymentStatus.FAILED)
        )
        if failed.rowcount == 0:
            return {"message": "Already processed"}
        await db.commit()

    return {"message": "Callback processed"}


@router.get("/my-payments", response_model=List[PaymentResponse])
async def get_my_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id, Payment.deleted_at.is_(None))
        .order_by(Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return payment


@router.get("/invoice/{invoice_id}", response_model=List[PaymentResponse])
async def get_payments_by_invoice(
    invoice_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.order))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if (
        invoice.order.created_by_user_id != current_user.id
        and invoice.order.assigned_to_user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Payment)
        .where(Payment.invoice_id == invoice_id, Payment.deleted_at.is_(None))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/pay-with-wallet/{invoice_id}")
async def pay_with_wallet(
    invoice_id: int,
    coupon_code: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pay an invoice using wallet balance with optional promo code (one-use-per-user enforced)."""
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.order).selectinload(Order.conversation))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found")

    payment_amount = invoice.full_amount
    discount_amount = 0
    coupon_used = None

    if coupon_code:
        result = await db.execute(
            select(Promocode).where(
                Promocode.code == coupon_code.upper(),
                Promocode.active == True,
                Promocode.deleted_at.is_(None),
            )
        )
        coupon = result.scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=400, detail="Invalid coupon code")

        if coupon.valid_until.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Coupon is expired")

        if coupon.usage_limit > 0 and coupon.usage_count >= coupon.usage_limit:
            raise HTTPException(status_code=400, detail="Coupon usage limit exceeded")

        if invoice.full_amount < coupon.minimum_order_value:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum order value for this coupon is {coupon.minimum_order_value / 100:.2f} SAR",
            )

        # Per-user one-use enforcement
        usage_check = await db.execute(
            select(PromocodeUsage).where(
                PromocodeUsage.user_id == current_user.id,
                PromocodeUsage.promocode_id == coupon.id,
            )
        )
        if usage_check.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="You have already used this promocode"
            )

        base = {
            "order_total": invoice.full_amount,
            "service_fee": invoice.service_fee,
            "delivery_fee": invoice.courier_fee,
        }.get(coupon.applicable_to, invoice.full_amount)

        discount_amount = int(base * coupon.percentage / 100)
        if coupon.max_value > 0:
            discount_amount = min(discount_amount, coupon.max_value)

        payment_amount = max(invoice.full_amount - discount_amount, 0)
        coupon_used = coupon

    # Atomic conditional deduction — prevents negative balance under concurrent requests
    deduct = await db.execute(
        update(Wallet)
        .where(Wallet.user_id == current_user.id, Wallet.balance >= payment_amount)
        .values(
            balance=Wallet.balance - payment_amount,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(Wallet.balance)
    )
    row = deduct.fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    await db.refresh(wallet)
    balance_before = wallet.balance + payment_amount  # balance before deduction

    try:

        invoice.status = InvoiceStatus.PAID
        invoice.updated_at = datetime.now(timezone.utc)

        if coupon_used:
            invoice.promocode_id = coupon_used.id
            invoice.discount_amount = discount_amount
            coupon_used.usage_count += 1
            coupon_used.updated_at = datetime.now(timezone.utc)
            # Record per-user usage
            db.add(PromocodeUsage(user_id=current_user.id, promocode_id=coupon_used.id))

        invoice.order.status = OrderStatus.PAID
        invoice.order.updated_at = datetime.now(timezone.utc)

        payment = Payment(
            invoice_id=invoice_id,
            user_id=current_user.id,
            amount=payment_amount,
            payment_method=PaymentMethod.WALLET,
            status=PaymentStatus.COMPLETED,
            payment_date=datetime.now(timezone.utc),
            wallet_balance_before=balance_before,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        if invoice.order.conversation:
            from models import Message
            from utils.websocket.websocket_events import emit_chat_message

            content = (
                f"تم دفع الفاتورة بنجاح - المبلغ المدفوع: {payment_amount / 100:.2f} ريال"
            )
            if coupon_used:
                content += f"\n(تم تطبيق خصم: {discount_amount / 100:.2f} ريال)"
            msg = Message(
                conversation_id=invoice.order.conversation.id,
                sender_id=current_user.id,
                content=content,
                message_type="text",
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            await emit_chat_message(
                invoice.order.conversation.id,
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "sender_id": msg.sender_id,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "sent_at": msg.sent_at.isoformat(),
                },
                db,
            )

        from utils.websocket.websocket_events import emit_order_status_change

        await emit_order_status_change(invoice.order.id, invoice.order.status.value)

        try:
            from tasks.email_tasks import send_invoice_email_task

            await send_invoice_email_task.kiq(invoice.id)
        except Exception as e:
            logging.error("Failed to enqueue invoice email for invoice %s: %s", invoice.id, str(e))

        return {
            "message": f"Payment successful{f'. Discount: {discount_amount / 100:.2f} SAR' if coupon_used else ''}",
            "payment_id": payment.id,
            "remaining_balance": wallet.balance,
            "final_amount": payment_amount,
            "discount_amount": discount_amount,
        }

    except Exception as e:
        logging.error("pay_with_wallet failed: %s", str(e))
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Something went wrong. Please contact administration."
        )
