import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.enums import InvoiceStatus as InvoiceStatusEnum
from models.enums import OrderStatus as OrderStatusEnum
from models.enums import PaymentMethod as PaymentMethodEnum
from models.enums import PaymentStatus as PaymentStatusEnum


def _normalize_optional_text(v):
    """Strip whitespace; return None if the result is empty."""
    if v is not None and len(v.strip()) == 0:
        return None
    return v


def _validate_event_title(v, *, required: bool = True):
    if v is None:
        return v
    v = v.strip()
    if required and not v:
        raise ValueError("Title is required")
    if not v:
        raise ValueError("Title cannot be empty")
    if len(v) > 200:
        raise ValueError("Title must be less than 200 characters")
    return v


def _validate_future_datetime(v):
    if v is None:
        return v
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    if v < datetime.now(timezone.utc):
        raise ValueError("Event date cannot be in the past")
    return v


class UpdateUserProfile(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    passport_id: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            if not re.match(
                r"^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-zA-Z0-9\s]{2,}$",
                v.strip(),
            ):
                raise ValueError(
                    "Name must contain only letters, numbers, and spaces, minimum 2 characters"
                )
            if len(v.strip()) < 2:
                raise ValueError("Name must be at least 2 characters long")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        if v is not None:
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 16:
                raise ValueError("User must be at least 16 years old")
            if v > today:
                raise ValueError("Date of birth cannot be in the future")
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

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, v):
        return _normalize_optional_text(v)


class CreateOrderWithImages(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    description: Optional[str] = None
    city_id: int
    delivery_date: datetime

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, v):
        return _normalize_optional_text(v)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    invoice: Optional[InvoiceResponse] = None


class CityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: Optional[str]
    active: bool


class CreateInvoice(BaseModel):
    order_id: int
    full_amount: float
    service_fee: Optional[float] = 0.0
    order_only_price: float
    courier_fee: Optional[float] = 0.0
    description: Optional[str] = Field(None, max_length=1000)
    comment: Optional[str] = Field(None, max_length=1000)
    due_date: Optional[datetime] = None
    tax_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0

    @field_validator(
        "full_amount",
        "service_fee",
        "order_only_price",
        "courier_fee",
        "tax_amount",
        "discount_amount",
    )
    @classmethod
    def validate_amount(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError("Amount cannot be negative")
            if round(v, 3) != v:
                raise ValueError("Amount must have at most 3 decimal places")
        return v


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class AssignOrderRequest(BaseModel):
    assigned_to_user_id: int


# Chat schemas
class CreateConversationRequest(BaseModel):
    other_user_id: int


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    courier_id: Optional[int]
    order_id: int
    status: str
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"
    media_type: Optional[str] = None
    invoice_description: Optional[str] = None
    invoice_gift_price: Optional[int] = None
    invoice_service_fee: Optional[int] = None
    invoice_delivery_fee: Optional[int] = None
    invoice_total: Optional[int] = None
    media_url: Optional[str] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: Optional[int]
    content: str
    sent_at: datetime
    message_type: str
    media_type: Optional[str]
    invoice_description: Optional[str]
    invoice_gift_price: Optional[int]
    invoice_service_fee: Optional[int]
    invoice_delivery_fee: Optional[int]
    invoice_total: Optional[int]
    media_url: Optional[str]


# Wallet schemas
class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    balance: int
    created_at: datetime
    updated_at: datetime


class CreateWallet(BaseModel):
    user_id: int
    balance: Optional[int] = 0


class UpdateWalletBalance(BaseModel):
    amount: int


class ChargeWalletRequest(BaseModel):
    amount: int

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError("Minimum charge amount is 10 riyals")
        if not isinstance(v, int):
            raise ValueError("Amount must be an integer")
        return v


class InitiateWalletChargeRequest(BaseModel):
    amount_sar: float = Field(..., gt=0)


class RequestWalletDeposit(BaseModel):
    amount: float

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError("Minimum deposit amount is 10 riyals")
        if round(v, 2) != v:
            raise ValueError("Amount must have exactly 2 decimal places")
        return v


# Payment schemas
class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str]
    percentage: int
    max_value: int
    minimum_order_value: int
    usage_limit: int
    usage_count: int
    valid_until: datetime
    active: bool
    applicable_to: str
    created_at: datetime
    updated_at: datetime


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
    code: str = Field(..., min_length=1, max_length=50)
    order_total: int = Field(..., ge=1)


# Important Events schemas
class CreateImportantEventRequest(BaseModel):
    title: str
    event_date: datetime
    recurring: Optional[bool] = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        return _validate_event_title(v, required=True)

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, v):
        return _validate_future_datetime(v)


class ImportantEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    event_date: datetime
    recurring: bool
    created_at: datetime
    updated_at: datetime


class UpdateImportantEventRequest(BaseModel):
    title: Optional[str] = None
    event_date: Optional[datetime] = None
    recurring: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        return _validate_event_title(v, required=False)

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, v):
        return _validate_future_datetime(v)


class CompleteProfileRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    date_of_birth: str
    timezone: Optional[str] = None
    role: str = "Customer"


class UpdateTimezoneRequest(BaseModel):
    timezone: str = Field(..., min_length=1)


class UpdatePushTokenRequest(BaseModel):
    push_token: str = Field(..., min_length=1, max_length=300)
