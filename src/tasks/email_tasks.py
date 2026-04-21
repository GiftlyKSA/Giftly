"""
Email tasks — run in a separate TaskIQ worker process.

Each task opens its own DB session so it is completely decoupled from the
FastAPI request lifecycle. The router only enqueues task IDs; it never passes
a DB session across the process boundary.

Worker startup command:
    taskiq worker tasks.broker:broker tasks.email_tasks
"""

import logging

from utils.database.database import AsyncSessionLocal

from utils.email.background_email import (
    send_invoice_email_background,
    send_payment_confirmation_email_background,
    send_welcome_email_background,
)

from .broker import broker

logger = logging.getLogger(__name__)


@broker.task
async def send_sms_task(phone: str, otp: str) -> None:
    """Send an OTP SMS via the configured SMS provider (non-blocking)."""
    from utils.clients.sms import send_sms
    await send_sms(phone, otp)


@broker.task
async def send_invoice_email_task(invoice_id: int) -> None:
    """Send the invoice email to the customer after an invoice is created."""
    async with AsyncSessionLocal() as db:
        await send_invoice_email_background(invoice_id, db)


@broker.task
async def send_welcome_email_task(user_id: int) -> None:
    """Send the welcome email to a newly registered user."""
    async with AsyncSessionLocal() as db:
        await send_welcome_email_background(user_id, db)


@broker.task
async def send_payment_confirmation_email_task(invoice_id: int) -> None:
    """Send a payment confirmation email after a successful payment."""
    async with AsyncSessionLocal() as db:
        await send_payment_confirmation_email_background(invoice_id, db)
