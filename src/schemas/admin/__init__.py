from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class OrderStatusEnum(str, Enum):
    NEW = "new"
    RECEIVED_BY_COURIER = "received by courier"
    INVOICE_CREATED = "invoice created"
    PAYMENT_PENDING = "payment pending"
    PAYMENT_AUTHORIZED = "payment authorized"
    AWAITING_PICKUP = "awaiting pickup"
    PAID = "paid"
    IN_PROGRESS_TO_DO = "in progress to do"
    CANCELLED = "cancelled"
    DONE = "done"
    IN_PROGRESS_TO_DELIVER = "in progress to deliver"
    OUT_FOR_DELIVERY = "out for delivery"
    AWAITING_CONFIRMATION = "awaiting confirmation"


class InvoiceStatusEnum(str, Enum):
    NEW = "new"
    DRAFT = "draft"
    PENDING_APPROVAL = "pending approval"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    OTHER = "other"


class SendOTP(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        if not re.match(r"^(\+966|0)?[5][0-9]{8}$", v):
            raise ValueError("Invalid Saudi phone number format")
        clean = re.sub(r"^(\+966|0)+", "", v)
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

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        if not re.match(r"^(\+966|0)?[5][0-9]{8}$", v):
            raise ValueError("Invalid Saudi phone number format")
        clean = re.sub(r"^(\+966|0)+", "", v)
        return clean

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be 6 digits")
        return v
