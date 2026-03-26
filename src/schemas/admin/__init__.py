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
