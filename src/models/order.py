from utils.database.database import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, nullable=False, unique=True)

    def __str__(self):
        return f"Order {self.order_id}"

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    description = Column(Text, nullable=True)
    creation_date = Column(DateTime, default=func.now(), nullable=False)
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.NEW)
    comments = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False)
    customer_confirmed = Column(
        Boolean, nullable=False, default=False
    )  # Customer confirms delivery before order goes DONE

    # Relationships
    created_by_user = relationship(
        "User", back_populates="created_orders", foreign_keys=[created_by_user_id]
    )
    assigned_to_user = relationship(
        "User", back_populates="assigned_orders", foreign_keys=[assigned_to_user_id]
    )
    city = relationship("City", back_populates="orders")
    # Relationship to invoice
    invoice = relationship(
        "Invoice", back_populates="order", uselist=False, lazy="selectin"
    )
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="order", uselist=False)
    # Relationship to images
    images = relationship("OrderImage", back_populates="order", uselist=False)

    __table_args__ = (
        Index("idx_order_created_by", "created_by_user_id", "creation_date"),
        Index("idx_order_assigned_to", "assigned_to_user_id", "status"),
        Index("idx_order_status", "status", "updated_at"),
        Index("idx_order_city", "city_id", "status"),
        Index("idx_order_delivery", "delivery_date"),
        Index("idx_order_admin", "status", "city_id", "creation_date"),
        Index(
            "idx_order_city_status_creator", "city_id", "status", "created_by_user_id"
        ),
    )


class OrderImage(Base):
    __tablename__ = "order_images"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    image1_url = Column(String, nullable=True)
    image2_url = Column(String, nullable=True)
    image3_url = Column(String, nullable=True)
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    order = relationship("Order", back_populates="images")

    __table_args__ = (Index("idx_order_image_order", "order_id"),)
