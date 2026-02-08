from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db_sync
from models import Wallet
from schemas import WalletResponse
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
