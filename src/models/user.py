from database import Base
from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    def __str__(self):
        return f"{self.name or 'No Name'} ({self.phone_number})"

    phone_number = Column(String, unique=True, index=True)
    email = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    is_verified = Column(Boolean, default=False)
    otp = Column(String, nullable=True)
    otp_created_at = Column(DateTime, default=func.now())
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER)
    last_activity = Column(
        DateTime, nullable=True
    )  # Track last user activity for session management

    # Relationship to refresh tokens
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    # Relationship to orders created by user
    created_orders = relationship(
        "Order",
        back_populates="created_by_user",
        foreign_keys="Order.created_by_user_id",
    )
    # Relationship to orders assigned to user
    assigned_orders = relationship(
        "Order",
        back_populates="assigned_to_user",
        foreign_keys="Order.assigned_to_user_id",
    )
    # Relationship to wallet
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    # Relationship to payments
    payments = relationship(
        "Payment", back_populates="user", cascade="all, delete-orphan"
    )
    # Relationship to invoices created by user
    created_invoices = relationship("Invoice", back_populates="created_by_user")
    # Relationship to courier profile
    courier_profile = relationship(
        "CourierProfile", back_populates="user", uselist=False
    )
    # Relationship to customer profile
    customer_profile = relationship(
        "CustomerProfile", back_populates="user", uselist=False
    )

    __table_args__ = (Index("idx_user_role", "role"),)
