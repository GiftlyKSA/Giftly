from utils.database.database import Base
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .enums import DepositRequestStatus


class DepositRequest(Base):
    __tablename__ = "deposit_requests"

    id = Column(Integer, primary_key=True, index=True)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        Enum(DepositRequestStatus), nullable=False, default=DepositRequestStatus.PENDING
    )
    amount = Column(Integer, nullable=False)  # Amount in cents/halaym
    wallet_balance_before = Column(
        Integer, nullable=False
    )  # Balance before request in cents/halaym
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to courier
    courier = relationship("User", backref="deposit_requests")

    __table_args__ = (
        Index("idx_deposit_request_courier", "courier_id", "created_at"),
        Index("idx_deposit_request_status", "status", "created_at"),
    )
