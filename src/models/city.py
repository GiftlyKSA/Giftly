from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    def __str__(self):
        return self.name
    icon = Column(String, nullable=True)
    active = Column(Boolean, default=True)

    # Relationship to users
    users = relationship("User", back_populates="city")
    # Relationship to orders
    orders = relationship("Order", back_populates="city")