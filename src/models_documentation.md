# Database Models Documentation

This document outlines the tables, fields, relationships, and indexes defined in `models.py`. It also includes suggestions for improvements and separation of concerns.

## Enums

### OrderStatus
- NEW = "new"
- RECEIVED_BY_COURIER = "received by courier"
- PAID = "paid"
- IN_PROGRESS_TO_DO = "in progress to do"
- CANCELLED = "cancelled"
- DONE = "done"
- IN_PROGRESS_TO_DELIVER = "in progress to deliver"

### InvoiceStatus
- NEW = "new"
- PAID = "paid"
- CANCELLED = "cancelled"
- REFUNDED = "refunded"
- OTHER = "other"

### PaymentMethod
- WALLET = "wallet"
- CREDIT_CARD = "credit_card"
- APPLE_PAY = "apple_pay"
- MADA = "mada"

### PaymentStatus
- PENDING = "pending"
- COMPLETED = "completed"
- FAILED = "failed"
- REFUNDED = "refunded"

### DepositRequestStatus
- PENDING = "pending"
- APPROVED = "approved"
- REJECTED = "rejected"

## Tables

### CourierBalanceAddition
**Table Name:** courier_balance_additions

**Fields:**
- id: Integer, primary_key=True, index=True
- invoice_id: Integer, ForeignKey("invoices.id"), nullable=False
- order_id: Integer, ForeignKey("orders.id"), nullable=False
- user_id: Integer, ForeignKey("users.id"), nullable=False  # User who paid
- payment_method: Enum(PaymentMethod), nullable=False
- balance_before: Integer, nullable=False  # Courier's wallet balance before addition
- amount_to_add: Integer, nullable=False  # Amount added to courier's wallet
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False

**Relationships:**
- invoice: relationship("Invoice", backref="courier_balance_additions")
- order: relationship("Order", backref="courier_balance_additions")
- user: relationship("User", backref="courier_balance_additions")

**Indexes:**
- idx_courier_balance_addition_invoice: ('invoice_id')
- idx_courier_balance_addition_order: ('order_id')
- idx_courier_balance_addition_user: ('user_id', 'created_at')
- idx_courier_balance_addition_created: ('created_at')

### User
**Table Name:** users

**Fields:**
- id: Integer, primary_key=True, index=True
- phone_number: String, unique=True, index=True
- email: String, unique=True, nullable=True
- name: String, nullable=True
- date_of_birth: Date, nullable=True
- national_id: String, nullable=True  # Optional for customers, mandatory for couriers
- passport_id: String, nullable=True  # Optional for customers, mandatory for couriers
- is_verified: Boolean, default=False
- otp: String, nullable=True
- otp_created_at: DateTime, default=func.now()
- is_admin: Boolean, default=False
- role: String, default='Customer'
- admin_username: String, unique=True, nullable=True
- admin_password_hash: String, nullable=True
- last_activity: DateTime, nullable=True  # Track last user activity for session management
- city_id: Integer, ForeignKey("cities.id"), nullable=True

**Relationships:**
- refresh_tokens: relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
- city: relationship("City", back_populates="users")
- created_orders: relationship("Order", back_populates="created_by_user", foreign_keys="Order.created_by_user_id")
- assigned_orders: relationship("Order", back_populates="assigned_to_user", foreign_keys="Order.assigned_to_user_id")
- wallet: relationship("Wallet", back_populates="user", uselist=False)
- payments: relationship("Payment", back_populates="user", cascade="all, delete-orphan")
- created_invoices: relationship("Invoice", back_populates="created_by_user")

**Indexes:**
- idx_user_role: ('role')
- idx_user_city: ('city_id')
- idx_user_admin: ('admin_username', postgresql_where=Column('is_admin') == True)

### City
**Table Name:** cities

**Fields:**
- id: Integer, primary_key=True, index=True
- name: String, nullable=False
- icon: String, nullable=True
- active: Boolean, default=True

**Relationships:**
- users: relationship("User", back_populates="city")
- orders: relationship("Order", back_populates="city")

### Order
**Table Name:** orders

**Fields:**
- id: Integer, primary_key=True, index=True
- order_id: String, nullable=False, unique=True
- created_by_user_id: Integer, ForeignKey("users.id"), nullable=False
- assigned_to_user_id: Integer, ForeignKey("users.id"), nullable=True
- description: Text, nullable=True
- creation_date: DateTime, default=func.now(), nullable=False
- delivery_date: DateTime(timezone=True), nullable=True
- status: Enum(OrderStatus), nullable=False, default=OrderStatus.NEW
- comments: Text, nullable=True
- updated_at: DateTime, default=func.now(), onupdate=func.now()
- city_id: Integer, ForeignKey("cities.id"), nullable=False
- image1_data: Text, nullable=True  # Base64 encoded image data
- image2_data: Text, nullable=True  # Base64 encoded image data
- image3_data: Text, nullable=True  # Base64 encoded image data

**Relationships:**
- created_by_user: relationship("User", back_populates="created_orders", foreign_keys=[created_by_user_id])
- assigned_to_user: relationship("User", back_populates="assigned_orders", foreign_keys=[assigned_to_user_id])
- city: relationship("City", back_populates="orders")
- invoice: relationship("Invoice", back_populates="order", uselist=False, lazy='selectin')
- conversation: relationship("Conversation", back_populates="order", uselist=False)

**Indexes:**
- idx_order_created_by: ('created_by_user_id', 'creation_date')
- idx_order_assigned_to: ('assigned_to_user_id', 'status')
- idx_order_status: ('status', 'updated_at')
- idx_order_city: ('city_id', 'status')
- idx_order_delivery: ('delivery_date')
- idx_order_admin: ('status', 'city_id', 'creation_date')

### Invoice
**Table Name:** invoices

**Fields:**
- id: Integer, primary_key=True, index=True
- invoice_id: String, unique=True, nullable=False, index=True
- order_id: Integer, ForeignKey("orders.id"), nullable=False
- created_by_user_id: Integer, ForeignKey("users.id"), nullable=False
- full_amount: Integer, nullable=False  # Amount in cents/halaym
- service_fee: Integer, nullable=False, default=0
- order_only_price: Integer, nullable=False
- courier_fee: Integer, nullable=False, default=0
- status: Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.NEW
- description: Text, nullable=True
- comment: Text, nullable=True
- sent_to_user_via_email: Boolean, default=False
- sent_at: DateTime, nullable=True
- due_date: DateTime, nullable=True
- tax_amount: Integer, nullable=False, default=0
- discount_amount: Integer, nullable=False, default=0
- promocode_id: Integer, ForeignKey("promocodes.id"), nullable=True  # Which promocode was used
- created_at: DateTime, default=func.now(), nullable=False
- updated_at: DateTime, default=func.now(), onupdate=func.now()

**Relationships:**
- order: relationship("Order", back_populates="invoice")
- created_by_user: relationship("User", back_populates="created_invoices")
- payments: relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
- promocode: relationship("Promocode", back_populates="invoices")

**Indexes:**
- idx_invoice_order: ('order_id')
- idx_invoice_status: ('status', 'due_date')
- idx_invoice_paid: ('status', 'sent_to_user_via_email')

### RefreshToken
**Table Name:** refresh_tokens

**Fields:**
- id: Integer, primary_key=True, index=True
- user_id: Integer, ForeignKey("users.id"), nullable=False, index=True
- token_hash: String, nullable=False
- expires_at: DateTime, nullable=False
- revoked: Boolean, default=False
- created_at: DateTime, default=func.now()

**Relationships:**
- user: relationship("User", back_populates="refresh_tokens")

**Indexes:**
- idx_refresh_user: ('user_id', 'revoked', 'expires_at')
- idx_refresh_expiry: ('expires_at', postgresql_where=Column('revoked') == False)

### Conversation
**Table Name:** conversations

**Fields:**
- id: Integer, primary_key=True, index=True
- customer_id: Integer, ForeignKey("users.id"), nullable=False, index=True
- courier_id: Integer, ForeignKey("users.id"), nullable=True, index=True  # Made nullable for orders without assigned courier
- order_id: Integer, ForeignKey("orders.id"), nullable=False, index=True  # Link to order
- status: String(20), nullable=False, default='active'
- created_at: DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP')

**Relationships:**
- customer: relationship("User", foreign_keys=[customer_id])
- courier: relationship("User", foreign_keys=[courier_id])
- order: relationship("Order", back_populates="conversation")  # Add relationship to order
- messages: relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

**Indexes:**
- idx_conversation_customer: ('customer_id', 'created_at')
- idx_conversation_courier: ('courier_id', 'created_at')
- idx_conversation_order: ('order_id', 'created_at')
- idx_conversation_status: ('status', 'created_at')

**Constraints:**
- UniqueConstraint('customer_id', 'order_id', name='unique_customer_order')

### Message
**Table Name:** messages

**Fields:**
- id: Integer, primary_key=True, index=True
- conversation_id: Integer, ForeignKey("conversations.id"), nullable=False, index=True
- sender_id: Integer, ForeignKey("users.id"), nullable=False, index=True
- content: Text, nullable=False
- sent_at: DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP')
- message_type: String(20), nullable=False, default='text'  # 'text', 'invoice', or 'image'
- invoice_description: Text, nullable=True
- invoice_gift_price: Integer, nullable=True  # in cents/halaym
- invoice_service_fee: Integer, nullable=True
- invoice_delivery_fee: Integer, nullable=True
- invoice_total: Integer, nullable=True
- image_data: Text, nullable=True  # Base64 encoded image data

**Relationships:**
- conversation: relationship("Conversation", back_populates="messages")
- sender: relationship("User")

**Indexes:**
- idx_message_conversation: ('conversation_id', 'sent_at')
- idx_message_sender: ('sender_id', 'sent_at')
- idx_message_type: ('message_type', 'sent_at')

### Wallet
**Table Name:** wallets

**Fields:**
- id: Integer, primary_key=True, index=True
- user_id: Integer, ForeignKey("users.id"), nullable=False, unique=True
- balance: Integer, nullable=False, default=0  # Amount in cents/halaym
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False
- updated_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False

**Relationships:**
- user: relationship("User", back_populates="wallet")

**Indexes:**
- idx_wallet_user: ('user_id')
- idx_wallet_balance: ('balance')

### Payment
**Table Name:** payments

**Fields:**
- id: Integer, primary_key=True, index=True
- invoice_id: Integer, ForeignKey("invoices.id"), nullable=False
- user_id: Integer, ForeignKey("users.id"), nullable=False
- amount: Integer, nullable=False  # Amount in cents/halaym
- payment_method: Enum(PaymentMethod), nullable=False
- status: Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING
- transaction_id: String, nullable=True  # From payment processor
- payment_date: DateTime, nullable=True  # When payment was processed
- payment_details: Text, nullable=True  # JSON string for method-specific details
- wallet_balance_before: Integer, nullable=True  # Balance before wallet payment (in cents/halaym)
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False
- updated_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False

**Relationships:**
- invoice: relationship("Invoice", back_populates="payments")
- user: relationship("User", back_populates="payments")

**Indexes:**
- idx_payment_invoice: ('invoice_id')
- idx_payment_user: ('user_id', 'created_at')
- idx_payment_status: ('status', 'payment_date')
- idx_payment_method: ('payment_method', 'status')

### Promocode
**Table Name:** promocodes

**Fields:**
- id: Integer, primary_key=True, index=True
- name: String, nullable=False  # Name of the promo
- code: String, unique=True, nullable=False, index=True  # Promo code
- description: Text, nullable=True  # Optional description
- percentage: Integer, nullable=False  # Discount percentage (0-100)
- max_value: Integer, nullable=False, default=0  # Max discount amount in cents (0 = no limit)
- minimum_order_value: Integer, nullable=False, default=0  # Min order value in cents to use promo
- usage_limit: Integer, nullable=False, default=0  # Total usage limit (0 = unlimited)
- usage_count: Integer, nullable=False, default=0  # Current usage count
- valid_until: DateTime, nullable=False  # Expiration date
- active: Boolean, nullable=False, default=True  # Is promo active
- applicable_to: String, nullable=False, default='order_total'  # What discount applies to
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False
- updated_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False

**Relationships:**
- invoices: relationship("Invoice", back_populates="promocode")

**Indexes:**
- idx_promocode_code: ('code')
- idx_promocode_active: ('active', 'valid_until')
- idx_promocode_valid: ('active', 'valid_until', 'usage_limit', 'usage_count')

### DepositRequest
**Table Name:** deposit_requests

**Fields:**
- id: Integer, primary_key=True, index=True
- courier_id: Integer, ForeignKey("users.id"), nullable=False, index=True
- status: Enum(DepositRequestStatus), nullable=False, default=DepositRequestStatus.PENDING
- amount: Integer, nullable=False  # Amount in cents/halaym
- wallet_balance_before: Integer, nullable=False  # Balance before request in cents/halaym
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False
- updated_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now(), nullable=False

**Relationships:**
- courier: relationship("User", backref="deposit_requests")

**Indexes:**
- idx_deposit_request_courier: ('courier_id', 'created_at')
- idx_deposit_request_status: ('status', 'created_at')

### Review
**Table Name:** reviews

**Fields:**
- id: Integer, primary_key=True, index=True
- reviewed_by: Integer, ForeignKey("users.id"), nullable=False  # Customer who left the review
- reviewed: Integer, ForeignKey("users.id"), nullable=False  # Courier being reviewed
- rate: Integer, nullable=False  # Rating from 0 to 5
- comment: Text, nullable=True  # Optional comment
- created_at: DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False

**Relationships:**
- reviewer: relationship("User", foreign_keys=[reviewed_by], backref="reviews_given")
- reviewed_user: relationship("User", foreign_keys=[reviewed], backref="reviews_received")

**Indexes:**
- idx_review_reviewer: ('reviewed_by', 'created_at')
- idx_review_reviewed: ('reviewed', 'created_at')
- idx_review_rate: ('rate')

## Improvement Tasks

### Separation of Concerns
- **Separate Enums:** Move all enum definitions to a separate file (e.g., `enums.py`) to improve modularity and reusability.
- **Separate Admin Model:** Extract admin-related fields from the `User` model (e.g., `is_admin`, `admin_username`, `admin_password_hash`) into a separate `Admin` model that inherits from or relates to `User`. This would separate concerns between regular users and administrative users.
- **Image Storage Refactor:** Currently, images are stored as base64-encoded text in fields like `Order.image1_data`, `Message.image_data`. Consider moving to a proper file storage system (e.g., using a cloud storage service or local file system) and storing file paths/URLs instead. Create a separate `Image` model to manage image metadata.
- **Message Types:** The `Message` model has fields for different message types (text, invoice, image). Consider creating separate models or a more polymorphic approach for different message types to avoid nullable fields and improve type safety.

### Performance and Design Improvements
- **Audit Logging:** Add audit fields (created_by, updated_by) to models that track who made changes, especially for sensitive data like payments and invoices.
- **Soft Deletes:** Implement soft delete functionality for critical models (e.g., `User`, `Order`, `Invoice`) by adding a `deleted_at` field instead of hard deletes.
- **Validation:** Add more constraints and validations at the model level (e.g., ensure `rate` in `Review` is between 0 and 5).
- **Indexing Review:** Review and optimize indexes based on query patterns. Some indexes might be redundant or missing.
- **Relationship Optimization:** Some relationships use `lazy='selectin'` or other loading strategies; ensure they match actual usage patterns to avoid N+1 queries.
- **Currency Handling:** Amounts are stored in cents/halaym; consider using a more robust money handling library or custom types for better precision and operations.
- **OTP Security:** The `otp` field in `User` is stored in plain text; consider hashing or encrypting sensitive fields like OTPs and tokens.

### Code Organization
- **Model Grouping:** Group related models into separate files (e.g., `user_models.py`, `order_models.py`, `payment_models.py`) to reduce the size of `models.py` and improve maintainability.
- **Base Model:** Create a base model class with common fields (id, created_at, updated_at) to reduce duplication.
- **Constants:** Extract magic numbers and strings (e.g., default values, limits) into constants at the top of the file or a separate constants file.