from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Wallet, DepositRequest, DepositRequestStatus, Payment, PaymentMethod, PaymentStatus
from schemas import WalletResponse, RequestWalletDeposit
from auth import get_current_user
from config import settings
from utils.clients.paylink import PaylinkClient

router = APIRouter()


@router.get("/my-wallet", response_model=WalletResponse)
async def get_my_wallet(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.post("/initiate-charge")
async def initiate_wallet_charge(
    data: dict,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate a wallet top-up via Paylink.sa.
    Returns a payment URL the client should open in-browser / in-app.
    Minimum charge: 10 SAR.
    """
    amount_sar = data.get("amount_sar")
    if not isinstance(amount_sar, (int, float)) or amount_sar < 10:
        raise HTTPException(status_code=400, detail="Minimum charge amount is 10 SAR")

    if not settings.paylink_api_key:
        raise HTTPException(
            status_code=503,
            detail="Payment gateway not configured. Contact support.",
        )

    # Create a PENDING payment record so we can match the callback
    amount_halaym = int(round(amount_sar * 100))
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    new_payment = Payment(
        invoice_id=None,          # wallet top-up, no invoice
        user_id=current_user.id,
        amount=amount_halaym,
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.PENDING,
    )
    db.add(new_payment)
    await db.commit()
    await db.refresh(new_payment)

    try:
        async with PaylinkClient(settings.paylink_api_key, settings.paylink_test_mode) as paylink:
            response = await paylink.create_order({
                "amount": float(amount_sar),
                "currency": "SAR",
                "description": f"Wallet top-up for user {current_user.id}",
                "customer": {
                    "name": current_user.name or "Customer",
                    "email": current_user.email or "",
                    "phone": current_user.phone_number,
                },
                "orderNumber": str(new_payment.id),
                "callBackUrl": settings.paylink_callback_url,
                "returnUrl": settings.paylink_return_url,
            })
    except Exception as e:
        # Roll back the pending payment if gateway call fails
        new_payment.status = PaymentStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {str(e)}")

    payment_url = response.get("url") or response.get("paymentUrl")
    transaction_id = response.get("transactionNo") or response.get("id")

    new_payment.transaction_id = str(transaction_id) if transaction_id else None
    await db.commit()

    return {
        "payment_url": payment_url,
        "payment_id": new_payment.id,
        "amount_sar": amount_sar,
        "status": "pending",
    }


@router.post("/request-deposit")
async def request_wallet_deposit(
    request: RequestWalletDeposit,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request a payout from courier wallet balance. Requires admin approval."""
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can request wallet deposits")

    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    amount_in_halaym = int(request.amount * 100)

    deposit_request = DepositRequest(
        courier_id=current_user.id,
        status=DepositRequestStatus.PENDING,
        amount=amount_in_halaym,
        wallet_balance_before=wallet.balance,
    )
    db.add(deposit_request)
    await db.commit()
    await db.refresh(deposit_request)

    return {
        "message": "تم إرسال طلب شحن المحفظة. سيتم مراجعة الطلب من قبل الإدارة.",
        "requested_amount": request.amount,
        "current_balance": wallet.balance / 100,
        "request_id": deposit_request.id,
    }
