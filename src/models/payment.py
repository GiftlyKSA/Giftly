from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from .enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in cents/halaym
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    transaction_id = Column(String, nullable=True)  # From payment processor
    payment_date = Column(DateTime, nullable=True)  # When payment was processed
    payment_details = Column(Text, nullable=True)  # JSON string for method-specific details
    wallet_balance_before = Column(Integer, nullable=True)  # Balance before wallet payment (in cents/halaym)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    user = relationship("User", back_populates="payments")

    __table_args__ = (
        Index('idx_payment_invoice', 'invoice_id'),
        Index('idx_payment_user', 'user_id', 'created_at'),
        Index('idx_payment_status', 'status', 'payment_date'),
        Index('idx_payment_method', 'payment_method', 'status'),
    )