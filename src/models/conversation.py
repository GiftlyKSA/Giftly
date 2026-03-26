from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from .enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Made nullable for orders without assigned courier
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)  # Link to order
    status = Column(Enum(ConversationStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]), nullable=False, default=ConversationStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    customer = relationship("User", foreign_keys=[customer_id])
    courier = relationship("User", foreign_keys=[courier_id])
    order = relationship("Order", back_populates="conversation")  # Add relationship to order
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_conversation_customer', 'customer_id', 'created_at'),
        Index('idx_conversation_courier', 'courier_id', 'created_at'),
        Index('idx_conversation_order', 'order_id', 'created_at'),
        Index('idx_conversation_status', 'status', 'created_at'),
        UniqueConstraint('customer_id', 'order_id', name='unique_customer_order'),  # Changed to order-based uniqueness
    )