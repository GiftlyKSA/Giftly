from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String, unique=True, nullable=False, index=True)

    def __str__(self):
        return f"Invoice {self.invoice_id}"
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    full_amount = Column(Integer, nullable=False)  # Amount in cents/halaym
    service_fee = Column(Integer, nullable=False, default=0)
    order_only_price = Column(Integer, nullable=False)
    courier_fee = Column(Integer, nullable=False, default=0)
    status = Column(Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.NEW)
    description = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    sent_to_user_via_email = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    tax_amount = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=True)  # Which promocode was used
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    order = relationship("Order", back_populates="invoice")
    created_by_user = relationship("User", back_populates="created_invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    promocode = relationship("Promocode", back_populates="invoices")

    __table_args__ = (
        Index('idx_invoice_order', 'order_id'),
        Index('idx_invoice_status', 'status', 'due_date'),
        Index('idx_invoice_paid', 'status', 'sent_to_user_via_email'),
    )