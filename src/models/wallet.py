from database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    balance = Column(Integer, nullable=False, default=0)  # Amount in cents/halaym
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to user
    user = relationship("User", back_populates="wallet")

    __table_args__ = (
        Index("idx_wallet_user", "user_id"),
        Index("idx_wallet_balance", "balance"),
    )
