from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import enum

class OrderStatus(enum.Enum):
    NEW = "new"
    RECEIVED_BY_COURIER = "received by courier"
    PAID = "paid"
    IN_PROGRESS_TO_DO = "in progress to do"
    CANCELLED = "cancelled"
    DONE = "done"
    IN_PROGRESS_TO_DELIVER = "in progress to deliver"

class InvoiceStatus(enum.Enum):
    NEW = "new"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    OTHER = "other"

class PaymentMethod(enum.Enum):
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"
    APPLE_PAY = "apple_pay"
    MADA = "mada"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

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
    is_admin = Column(Boolean, default=False)
    role = Column(String, default='Customer')
    admin_username = Column(String, unique=True, nullable=True)
    admin_password_hash = Column(String, nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)

    # Relationship to JWT tokens
    jwt_tokens = relationship("JWTToken", back_populates="user", cascade="all, delete-orphan")
    # Relationship to city
    city = relationship("City", back_populates="users")
    # Relationship to orders created by user
    created_orders = relationship("Order", back_populates="created_by_user", foreign_keys="Order.created_by_user_id")
    # Relationship to orders assigned to user
    assigned_orders = relationship("Order", back_populates="assigned_to_user", foreign_keys="Order.assigned_to_user_id")
    # Relationship to wallet
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    # Relationship to payments
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    # Relationship to invoices created by user
    created_invoices = relationship("Invoice", back_populates="created_by_user")

    __table_args__ = (
        Index('idx_user_role', 'role'),
        Index('idx_user_city', 'city_id'),
        Index('idx_user_admin', 'admin_username', postgresql_where=Column('is_admin') == True),
    )

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
    delivery_date = Column(DateTime, nullable=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.NEW)
    comments = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False)

    # Relationships
    created_by_user = relationship("User", back_populates="created_orders", foreign_keys=[created_by_user_id])
    assigned_to_user = relationship("User", back_populates="assigned_orders", foreign_keys=[assigned_to_user_id])
    city = relationship("City", back_populates="orders")
    # Relationship to invoice
    invoice = relationship("Invoice", back_populates="order", uselist=False)
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="order", uselist=False)

    __table_args__ = (
        Index('idx_order_created_by', 'created_by_user_id', 'creation_date'),
        Index('idx_order_assigned_to', 'assigned_to_user_id', 'status'),
        Index('idx_order_status', 'status', 'updated_at'),
        Index('idx_order_city', 'city_id', 'status'),
        Index('idx_order_delivery', 'delivery_date'),
        Index('idx_order_admin', 'status', 'city_id', 'creation_date'),
    )

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

class JWTToken(Base):
    __tablename__ = "jwt_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String, unique=True, nullable=False, index=True)
    refresh_token = Column(String, unique=True, nullable=False, index=True)
    access_token_expires_at = Column(DateTime, nullable=False)
    refresh_token_expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Relationship back to user
    user = relationship("User", back_populates="jwt_tokens")

    __table_args__ = (
        Index('idx_jwt_user', 'user_id', 'is_revoked', 'access_token_expires_at'),
        Index('idx_jwt_expiry', 'access_token_expires_at', postgresql_where=Column('is_revoked') == False),
    )

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Made nullable for orders without assigned courier
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)  # Link to order
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))

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

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    message_type = Column(String(20), nullable=False, default='text')  # 'text' or 'invoice'
    # Invoice specific fields
    invoice_description = Column(Text, nullable=True)
    invoice_gift_price = Column(Integer, nullable=True)  # in cents/halaym
    invoice_service_fee = Column(Integer, nullable=True)
    invoice_delivery_fee = Column(Integer, nullable=True)
    invoice_total = Column(Integer, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")

    __table_args__ = (
        Index('idx_message_conversation', 'conversation_id', 'sent_at'),
        Index('idx_message_sender', 'sender_id', 'sent_at'),
        Index('idx_message_type', 'message_type', 'sent_at'),
    )

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    balance = Column(Integer, nullable=False, default=0)  # Amount in cents/halaym
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    # Relationship to user
    user = relationship("User", back_populates="wallet")

    __table_args__ = (
        Index('idx_wallet_user', 'user_id'),
        Index('idx_wallet_balance', 'balance'),
    )

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

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    user = relationship("User", back_populates="payments")

    __table_args__ = (
        Index('idx_payment_invoice', 'invoice_id'),
        Index('idx_payment_user', 'user_id', 'created_at'),
        Index('idx_payment_status', 'status', 'payment_date'),
        Index('idx_payment_method', 'payment_method', 'status'),
    )

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

    def __str__(self):
        return f"{self.name} ({self.code})"

    # Relationships
    invoices = relationship("Invoice", back_populates="promocode")

    __table_args__ = (
        Index('idx_promocode_code', 'code'),
        Index('idx_promocode_active', 'active', 'valid_until'),
        Index('idx_promocode_valid', 'active', 'valid_until', 'usage_limit', 'usage_count'),
    )
