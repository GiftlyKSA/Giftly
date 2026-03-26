from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from .enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False)
    jti = Column(String, nullable=True, unique=True, index=True)  # JWT ID for O(1) token lookup
    device_id = Column(String, nullable=True)  # Optional device identifier
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Relationship back to user
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index('idx_refresh_user', 'user_id', 'revoked', 'expires_at'),
        Index('idx_refresh_device', 'user_id', 'device_id'),
        Index('idx_refresh_expiry', 'expires_at', postgresql_where=Column('revoked') == False),
    )