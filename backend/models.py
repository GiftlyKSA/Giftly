from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint, Index, text, select
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from enums import OrderStatus, InvoiceStatus, PaymentMethod, PaymentStatus, DepositRequestStatus, UserRole, ConversationStatus
from sqlalchemy import event

class CourierBalanceAddition(Base):
    __tablename__ = "courier_balance_additions"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who paid
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    balance_before = Column(Integer, nullable=False)  # Courier's wallet balance before addition
    amount_to_add = Column(Integer, nullable=False)  # Amount added to courier's wallet
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    # Relationships
    invoice = relationship("Invoice", backref="courier_balance_additions")
    order = relationship("Order", backref="courier_balance_additions")
    user = relationship("User", backref="courier_balance_additions")

    __table_args__ = (
        Index('idx_courier_balance_addition_invoice', 'invoice_id'),
        Index('idx_courier_balance_addition_order', 'order_id'),
        Index('idx_courier_balance_addition_user', 'user_id', 'created_at'),
        Index('idx_courier_balance_addition_created', 'created_at'),
    )

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
    last_activity = Column(DateTime, nullable=True)  # Track last user activity for session management

    # Relationship to refresh tokens
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
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
    # Relationship to courier profile
    courier_profile = relationship("CourierProfile", back_populates="user", uselist=False)
    # Relationship to customer profile
    customer_profile = relationship("CustomerProfile", back_populates="user", uselist=False)

    __table_args__ = (
        Index('idx_user_role', 'role'),
    )

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    def __str__(self):
        return f"{self.name or self.username}"

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
    rate = Column(Integer, nullable=False, default=0)  # Average rating * 10 (e.g., 45 for 4.5)
    is_available = Column(Boolean, nullable=False, default=True)   # Courier can toggle on/off availability
    is_approved = Column(Boolean, nullable=False, default=False)   # Admin must approve before courier is active
    push_token = Column(String, nullable=True)                     # FCM / APNs push notification token
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="courier_profile")
    city = relationship("City")

    __table_args__ = (
        Index('idx_courier_profile_user', 'user_id'),
        Index('idx_courier_profile_city', 'city_id'),
    )

    def get_average_rate(self):
        """Return average rate as float (rate / 10)"""
        return self.rate / 10.0 if self.rate > 0 else 0.0

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    timezone = Column(String, nullable=True)  # User's timezone
    push_token = Column(String, nullable=True)  # FCM / APNs push notification token
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="customer_profile")

    __table_args__ = (
        Index('idx_customer_profile_user', 'user_id'),
    )

class ImportantEvent(Base):
    __tablename__ = "important_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    event_date = Column(DateTime, nullable=False)
    recurring = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="important_events")

    __table_args__ = (
        Index('idx_important_event_user', 'user_id', 'event_date'),
        Index('idx_important_event_date', 'event_date'),
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
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.NEW)
    comments = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False)
    customer_confirmed = Column(Boolean, nullable=False, default=False)  # Customer confirms delivery before order goes DONE

    # Relationships
    created_by_user = relationship("User", back_populates="created_orders", foreign_keys=[created_by_user_id])
    assigned_to_user = relationship("User", back_populates="assigned_orders", foreign_keys=[assigned_to_user_id])
    city = relationship("City", back_populates="orders")
    # Relationship to invoice
    invoice = relationship("Invoice", back_populates="order", uselist=False, lazy='selectin')
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="order", uselist=False)
    # Relationship to images
    images = relationship("OrderImage", back_populates="order", uselist=False)

    __table_args__ = (
        Index('idx_order_created_by', 'created_by_user_id', 'creation_date'),
        Index('idx_order_assigned_to', 'assigned_to_user_id', 'status'),
        Index('idx_order_status', 'status', 'updated_at'),
        Index('idx_order_city', 'city_id', 'status'),
        Index('idx_order_delivery', 'delivery_date'),
        Index('idx_order_admin', 'status', 'city_id', 'creation_date'),
    )

class OrderImage(Base):
    __tablename__ = "order_images"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    image1_url = Column(String, nullable=True)
    image2_url = Column(String, nullable=True)
    image3_url = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="images")

    __table_args__ = (
        Index('idx_order_image_order', 'order_id'),
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

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False)
    jti = Column(String, nullable=True, unique=True, index=True)  # JWT ID for O(1) token lookup
    device_id = Column(String, nullable=True)  # Optional device identifier
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Relationship back to user
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index('idx_refresh_user', 'user_id', 'revoked', 'expires_at'),
        Index('idx_refresh_device', 'user_id', 'device_id'),
        Index('idx_refresh_expiry', 'expires_at', postgresql_where=Column('revoked') == False),
    )



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

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for system messages
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    message_type = Column(String(20), nullable=False, default='text')  # 'text', 'invoice', 'image', 'video', 'system'
    media_type = Column(String(20), nullable=True)  # 'image' or 'video' when message_type is 'image' or 'video'
    # Invoice specific fields
    invoice_description = Column(Text, nullable=True)
    invoice_gift_price = Column(Integer, nullable=True)  # in cents/halaym
    invoice_service_fee = Column(Integer, nullable=True)
    invoice_delivery_fee = Column(Integer, nullable=True)
    invoice_total = Column(Integer, nullable=True)
    # Media specific fields
    media_url = Column(String, nullable=True)  # URL to uploaded media file
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")

    __table_args__ = (
        Index('idx_message_conversation', 'conversation_id', 'sent_at'),
        Index('idx_message_sender', 'sender_id', 'sent_at'),
        Index('idx_message_type', 'message_type', 'sent_at'),
        Index('idx_message_media_type', 'media_type'),
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

class DepositRequest(Base):
    __tablename__ = "deposit_requests"

    id = Column(Integer, primary_key=True, index=True)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(Enum(DepositRequestStatus), nullable=False, default=DepositRequestStatus.PENDING)
    amount = Column(Integer, nullable=False)  # Amount in cents/halaym
    wallet_balance_before = Column(Integer, nullable=False)  # Balance before request in cents/halaym
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False)

    # Relationship to courier
    courier = relationship("User", backref="deposit_requests")

    __table_args__ = (
        Index('idx_deposit_request_courier', 'courier_id', 'created_at'),
        Index('idx_deposit_request_status', 'status', 'created_at'),
    )

class CourierReview(Base):
    __tablename__ = "courier_reviews"

    id = Column(Integer, primary_key=True, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Customer who left the review
    reviewed = Column(Integer, ForeignKey("users.id"), nullable=False)  # Courier being reviewed
    rate = Column(Integer, nullable=False)  # Rating from 0 to 5
    comment = Column(Text, nullable=True)  # Optional comment
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="courier_reviews_given")
    reviewed_user = relationship("User", foreign_keys=[reviewed], backref="courier_reviews_received")

    __table_args__ = (
        Index('idx_courier_review_reviewer', 'reviewed_by', 'created_at'),
        Index('idx_courier_review_reviewed', 'reviewed', 'created_at'),
        Index('idx_courier_review_rate', 'rate'),
    )

class PromocodeUsage(Base):
    """Tracks which user has used which promocode — enforces one-use-per-user limit."""
    __tablename__ = "promocode_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=False)
    used_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    user = relationship("User")
    promocode = relationship("Promocode")

    __table_args__ = (
        UniqueConstraint('user_id', 'promocode_id', name='uq_user_promocode'),
        Index('idx_promocode_usage_user', 'user_id'),
        Index('idx_promocode_usage_code', 'promocode_id'),
    )


# Event listener to update courier rate when review is added/updated/deleted
@event.listens_for(CourierReview, 'after_insert')
@event.listens_for(CourierReview, 'after_update')
@event.listens_for(CourierReview, 'after_delete')
def update_courier_rate(mapper, connection, target):
    # Recalculate average rate for the courier
    courier_id = target.reviewed
    result = connection.execute(
        select(func.avg(CourierReview.rate)).where(
            CourierReview.reviewed == courier_id,
            CourierReview.deleted_at.is_(None)
        )
    )
    avg_rate = result.scalar()
    if avg_rate is not None:
        new_rate = int(avg_rate * 10)
    else:
        new_rate = 0

    # Update courier profile
    connection.execute(
        CourierProfile.__table__.update().where(
            CourierProfile.user_id == courier_id
        ).values(rate=new_rate)
    )
