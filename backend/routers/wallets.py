from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db_sync
from models import Wallet, DepositRequest, DepositRequestStatus
from schemas import WalletResponse, ChargeWalletRequest, RequestWalletDeposit
from auth import get_current_user

router = APIRouter()

@router.get("/my-wallet", response_model=WalletResponse)
def get_my_wallet(current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Get current user's wallet.
    """
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet

@router.post("/charge-wallet")
def charge_wallet(request: ChargeWalletRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Charge wallet with specified amount in riyals.
    """
    # Get user's wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Add amount to wallet balance (amount is already in riyals)
    wallet.balance += request.amount
    wallet.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(wallet)

    return {
        "message": f"*تم شحن المحفظة بمبلغ {request.amount} ريال. الرصيد الجديد: {wallet.balance} ريال.*",
        "new_balance": wallet.balance
    }

@router.post("/request-deposit")
def request_wallet_deposit(request: RequestWalletDeposit, current_user=Depends(get_current_user), db: Session = Depends(get_db_sync)):
    """
    Request a wallet deposit. Only couriers can request deposits.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can request wallet deposits")

    # Get user's wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Convert amount from riyals to cents/halaym (multiply by 100)
    amount_in_cents = int(request.amount * 100)

    # Create deposit request record
    deposit_request = DepositRequest(
        courier_id=current_user.id,
        status=DepositRequestStatus.PENDING,
        amount=amount_in_cents,
        wallet_balance_before=wallet.balance
    )

    db.add(deposit_request)
    db.commit()
    db.refresh(deposit_request)

    return {
        "message": f"تم إرسال طلب شحن المحفظة بمبلغ {request.amount} ريال. سيتم مراجعة الطلب من قبل الإدارة.",
        "requested_amount": request.amount,
        "current_balance": wallet.balance / 100,  # Convert back to riyals for display
        "request_id": deposit_request.id
    }
