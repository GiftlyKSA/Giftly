from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from utils.database.database import Base

from .enums import PaymentMethod


class CourierBalanceAddition(Base):
    __tablename__ = "courier_balance_additions"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    balance_before = Column(Integer, nullable=False)
    amount_to_add = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    invoice = relationship("Invoice", backref="courier_balance_additions")
    order = relationship("Order", backref="courier_balance_additions")
    user = relationship("User", backref="courier_balance_additions")
