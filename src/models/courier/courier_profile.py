from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum,
    UniqueConstraint,
    Index,
    text,
    select,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from ..enums import (
    OrderStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    DepositRequestStatus,
    UserRole,
    ConversationStatus,
)
from sqlalchemy import event


class CourierProfile(Base):
    __tablename__ = "courier_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    national_id = Column(String, nullable=True)
    passport_id = Column(String, nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False)  # mandatory
    iban = Column(String, nullable=False)  # mandatory
    vehicle = Column(String, nullable=True)
    license = Column(String, nullable=True)
    rate = Column(
        Integer, nullable=False, default=0
    )  # Average rating * 10 (e.g., 45 for 4.5)
    is_available = Column(
        Boolean, nullable=False, default=True
    )  # Courier can toggle on/off availability
    is_approved = Column(
        Boolean, nullable=False, default=False
    )  # Admin must approve before courier is active
    push_token = Column(String, nullable=True)  # FCM / APNs push notification token
    specialties = Column(
        JSON, nullable=True
    )  # List of gift types handled: ["birthday", "anniversary", "flowers"]
    max_concurrent_orders = Column(
        Integer, nullable=False, default=3
    )  # Max orders courier can handle simultaneously
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="courier_profile")
    city = relationship("City")

    __table_args__ = (
        Index("idx_courier_profile_user", "user_id"),
        Index("idx_courier_profile_city", "city_id"),
        Index(
            "idx_courier_profile_available", "is_approved", "is_available", "city_id"
        ),
    )

    def get_average_rate(self):
        """Return average rate as float (rate / 10)"""
        return self.rate / 10.0 if self.rate > 0 else 0.0
