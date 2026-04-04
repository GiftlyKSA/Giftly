"""
SMS utility stub.

To go live:
1. Set SMS_PROVIDER_ENABLED=true in .env
2. Replace the body of send_sms() with your provider's SDK call
   (Unifonic, MSGSaudi, Twilio, etc.)
3. The OTP is intentionally NOT returned in any HTTP response —
   it is delivered exclusively through this function.
"""

import logging

from config import settings

logger = logging.getLogger(__name__)


async def send_sms(phone: str, otp: str) -> None:
    """
    Send an OTP to `phone` via the configured SMS provider.

    Args:
        phone: Normalized phone number, e.g. "559xxxxxxx"
        otp:   6-digit one-time password
    """
    if not settings.sms_provider_enabled:
        # Development mode: log to server console only, never expose in API response
        logger.info("[SMS STUB] OTP for %s: %s", phone, otp)
        return

    # TODO: replace with real provider call, e.g.:
    # async with httpx.AsyncClient() as client:
    #     await client.post(
    #         "https://api.unifonic.com/rest/SMS/messages",
    #         json={"AppSid": settings.sms_app_sid,
    #               "Recipient": f"966{phone}",
    #               "Body": f"رمز التحقق الخاص بك هو: {otp}"}
    #     )
    raise NotImplementedError(
        "SMS provider is enabled but not configured. "
        "Implement send_sms() in utils/sms.py."
    )
