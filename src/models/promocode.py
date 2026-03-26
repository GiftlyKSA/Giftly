from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from .enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class Promocode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Name of the promo
    code = Column(String, unique=True, nullable=False, index=True)  # Promo code
    description = Column(Text, nullable=True)  # Optional description
    percentage = Column(Integer, nullable=False)  # Discount percentage (0-100)
    max_value = Column(Integer, nullable=False, default=0)  # Max discount amount in cents (0 = no limit)
    minimum_order_value = Column(Integer, nullable=False, default=0)  # Min order value in cents to use promo
    usage_limit = Column(Integer, nullable=False, default=0)  # Total usage limit (0 = unlimited)
    usage_count = Column(Integer, nullable=False, default=0)  # Current usage count
    valid_until = Column(DateTime, nullable=False)  # Expiration date
    active = Column(Boolean, nullable=False, default=True)  # Is promo active
    applicable_to = Column(String, nullable=False, default='order_total')  # What discount applies to
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    def __str__(self):
        return f"{self.name} ({self.code})"

    # Relationships
    invoices = relationship("Invoice", back_populates="promocode")

    __table_args__ = (
        Index('idx_promocode_code', 'code'),
        Index('idx_promocode_active', 'active', 'valid_until'),
        Index('idx_promocode_valid', 'active', 'valid_until', 'usage_limit', 'usage_count'),
    )