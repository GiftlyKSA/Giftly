from __future__ import annotations

import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from models.enums import InvoiceStatus as InvoiceStatusEnum  # noqa: F401 — re-exported
from models.enums import OrderStatus as OrderStatusEnum  # noqa: F401 — re-exported

_SAUDI_PHONE_RE = re.compile(r"^(\+966|0)?[5][0-9]{8}$")


def _clean_saudi_phone(v: str) -> str:
    if not _SAUDI_PHONE_RE.match(v):
        raise ValueError("Invalid Saudi phone number format")
    return re.sub(r"^(\+966|0)+", "", v)


class SendOTP(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        return _clean_saudi_phone(v)


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
        return _clean_saudi_phone(v)

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be 6 digits")
        return v
