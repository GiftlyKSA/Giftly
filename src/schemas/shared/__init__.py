from __future__ import annotations

from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import date, datetime
import re
from enum import Enum

class OrderStatusEnum(str, Enum):
    NEW = "new"
    RECEIVED_BY_COURIER = "received by courier"
    PAID = "paid"
    IN_PROGRESS_TO_DO = "in progress to do"
    CANCELLED = "cancelled"
    DONE = "done"
    IN_PROGRESS_TO_DELIVER = "in progress to deliver"

class InvoiceStatusEnum(str, Enum):
    NEW = "new"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    OTHER = "other"

class SendOTP(BaseModel):
    phone_number: str

    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Basic phone number validation (Saudi format)
        if not re.match(r'^(\+966|0)?[5][0-9]{8}$', v):
            raise ValueError('Invalid Saudi phone number format')

        # Normalize phone number by removing leading zeros
        # Convert "0559644339" to "559644339"
        clean = re.sub(r'^(\+966|0)+', '', v)
        return clean

class OTPVerify(BaseModel):
    phone_number: str
    otp: str
    device_id: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    passport_id: Optional[str] = None
    timezone: Optional[str] = None

    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^(\+966|0)?[5][0-9]{8}$', v):
            raise ValueError('Invalid Saudi phone number format')

        # Normalize phone number by removing leading zeros
        # Convert "0559644339" to "559644339"
        clean = re.sub(r'^(\+966|0)+', '', v)
        return clean

    @validator('otp')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be 6 digits')
        return v

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            # Allow Arabic and English letters, spaces, minimum 2 characters
            if not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-zA-Z\s]{2,}$', v.strip()):
                raise ValueError('Name must contain only letters and spaces, minimum 2 characters')
            if len(v.strip()) < 2:
                raise ValueError('Name must be at least 2 characters long')
        return v

    @validator('date_of_birth')
    def validate_date_of_birth(cls, v):
        if v is not None:
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 16:
                raise ValueError('User must be at least 16 years old')
            if v > today:
                raise ValueError('Date of birth cannot be in the future')
        return v

class UpdateUserProfile(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    passport_id: Optional[str] = None
    timezone: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            if not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-zA-Z0-9\s]{2,}$', v.strip()):
                raise ValueError('Name must contain only letters, numbers, and spaces, minimum 2 characters')
            if len(v.strip()) < 2:
                raise ValueError('Name must be at least 2 characters long')
        return v

    @validator('date_of_birth')
    def validate_date_of_birth(cls, v):
        if v is not None:
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 16:
                raise ValueError('User must be at least 16 years old')
            if v > today:
                raise ValueError('Date of birth cannot be in the future')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    needs_profile: bool = False

class TokenData(BaseModel):
    phone_number: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class CreateOrder(BaseModel):
    description: Optional[str] = None
    city_id: int
    delivery_date: datetime
    image1_data: Optional[str] = None  # Base64 encoded image data
    image2_data: Optional[str] = None  # Base64 encoded image data
    image3_data: Optional[str] = None  # Base64 encoded image data

    @validator('description')
    def validate_description(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None  # Treat empty strings as None
        return v

# New schema for order creation with file uploads
class CreateOrderWithImages(BaseModel):
    description: Optional[str] = None
    city_id: int
    delivery_date: datetime

    @validator('description')
    def validate_description(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None  # Treat empty strings as None
        return v

    class Config:
        arbitrary_types_allowed = True

class InvoiceResponse(BaseModel):
    id: int
    invoice_id: str
    order_id: int
    full_amount: int
    service_fee: int
    order_only_price: int
    courier_fee: int
    status: InvoiceStatusEnum
    description: Optional[str]
    comment: Optional[str]
    sent_to_user_via_email: bool
    sent_at: Optional[datetime]
    due_date: Optional[datetime]
    tax_amount: int
    discount_amount: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    order_id: str
    created_by_user_id: int
    assigned_to_user_id: Optional[int]
    description: Optional[str]
    creation_date: datetime
    delivery_date: Optional[datetime]
    status: OrderStatusEnum
    comments: Optional[str]
    updated_at: datetime
    city_id: int
    invoice: Optional[InvoiceResponse] = None  # Include invoice information

    class Config:
        from_attributes = True

class CityResponse(BaseModel):
    id: int
    name: str
    icon: Optional[str]
    active: bool

    class Config:
        from_attributes = True

class CreateInvoice(BaseModel):
    order_id: int
    full_amount: float
    service_fee: Optional[float] = 0.0
    order_only_price: float
    courier_fee: Optional[float] = 0.0
    description: Optional[str] = None
    comment: Optional[str] = None
    due_date: Optional[datetime] = None
    tax_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0

    @validator('full_amount', 'service_fee', 'order_only_price', 'courier_fee', 'tax_amount', 'discount_amount')
    def validate_amount(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError('Amount cannot be negative')
            # Check for at most 3 decimal places
            if round(v, 3) != v:
                raise ValueError('Amount must have at most 3 decimal places')
        return v

class CancelOrderRequest(BaseModel):
    reason: str

class AssignOrderRequest(BaseModel):
    assigned_to_user_id: int

# Chat schemas
class CreateConversationRequest(BaseModel):
    other_user_id: int  # The ID of the other user (customer or courier)

class ConversationResponse(BaseModel):
    id: int
    customer_id: int
    courier_id: Optional[int]
    order_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"  # "text", "invoice", "image", "video", "system"
    media_type: Optional[str] = None  # "image" or "video" when message_type is "image" or "video"
    invoice_description: Optional[str] = None
    invoice_gift_price: Optional[int] = None
    invoice_service_fee: Optional[int] = None
    invoice_delivery_fee: Optional[int] = None
    invoice_total: Optional[int] = None
    media_url: Optional[str] = None  # URL to uploaded media file

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: Optional[int]  # Nullable for system messages
    content: str
    sent_at: datetime
    message_type: str
    media_type: Optional[str]
    invoice_description: Optional[str]
    invoice_gift_price: Optional[int]
    invoice_service_fee: Optional[int]
    invoice_delivery_fee: Optional[int]
    invoice_total: Optional[int]
    media_url: Optional[str]  # URL to uploaded media file

    class Config:
        from_attributes = True

# Wallet schemas
class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreateWallet(BaseModel):
    user_id: int
    balance: Optional[int] = 0

class UpdateWalletBalance(BaseModel):
    amount: int  # Positive for deposit, negative for withdrawal

class ChargeWalletRequest(BaseModel):
    amount: int  # Amount to charge in riyals (not cents)

    @validator('amount')
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError('Minimum charge amount is 10 riyals')
        if not isinstance(v, int):
            raise ValueError('Amount must be an integer')
        return v

class RequestWalletDeposit(BaseModel):
    amount: float  # Amount to request in riyals with decimals

    @validator('amount')
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError('Minimum deposit amount is 10 riyals')
        # Check for exactly 2 decimal places
        if round(v, 2) != v:
            raise ValueError('Amount must have exactly 2 decimal places')
        return v

# Payment schemas
class PaymentMethodEnum(str, Enum):
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"
    APPLE_PAY = "apple_pay"
    MADA = "mada"

class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    user_id: int
    amount: int
    payment_method: PaymentMethodEnum
    status: PaymentStatusEnum
    transaction_id: Optional[str]
    payment_date: Optional[datetime]
    payment_details: Optional[str]
    wallet_balance_before: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreatePayment(BaseModel):
    invoice_id: int
    user_id: int
    amount: int
    payment_method: PaymentMethodEnum
    transaction_id: Optional[str] = None
    payment_details: Optional[str] = None

class UpdatePaymentStatus(BaseModel):
    status: PaymentStatusEnum
    transaction_id: Optional[str] = None
    payment_date: Optional[datetime] = None

# Promocode schemas
class PromocodeResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    percentage: int
    max_value: int
    minimum_order_value: int
    usage_count: int
    valid_until: datetime
    active: bool
    applicable_to: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreatePromocode(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    percentage: int
    max_value: Optional[int] = 0
    minimum_order_value: Optional[int] = 0
    usage_limit: Optional[int] = 0
    valid_until: datetime
    active: Optional[bool] = True
    applicable_to: str = "order_total"

class UpdatePromocode(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    percentage: Optional[int] = None
    max_value: Optional[int] = None
    minimum_order_value: Optional[int] = None
    usage_limit: Optional[int] = None
    valid_until: Optional[datetime] = None
    active: Optional[bool] = None
    applicable_to: Optional[str] = None

class ApplyPromocodeRequest(BaseModel):
    code: str
    order_total: int

# Important Events schemas
class CreateImportantEventRequest(BaseModel):
    title: str
    event_date: datetime
    recurring: Optional[bool] = False

    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Title is required')
        if len(v.strip()) > 200:
            raise ValueError('Title must be less than 200 characters')
        return v.strip()

    @validator('event_date')
    def validate_event_date(cls, v):
        if v < datetime.utcnow():
            raise ValueError('Event date cannot be in the past')
        return v

class ImportantEventResponse(BaseModel):
    id: int
    user_id: int
    title: str
    event_date: datetime
    recurring: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UpdateImportantEventRequest(BaseModel):
    title: Optional[str] = None
    event_date: Optional[datetime] = None
    recurring: Optional[bool] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Title cannot be empty')
            if len(v.strip()) > 200:
                raise ValueError('Title must be less than 200 characters')
            return v.strip()
        return v

    @validator('event_date')
    def validate_event_date(cls, v):
        if v is not None and v < datetime.utcnow():
            raise ValueError('Event date cannot be in the past')
        return v