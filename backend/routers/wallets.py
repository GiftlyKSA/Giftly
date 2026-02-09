from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db_sync
from models import Wallet
from schemas import WalletResponse, ChargeWalletRequest
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
