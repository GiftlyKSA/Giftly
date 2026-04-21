"""
Unified async email providers.

Supported providers (set EMAIL_PROVIDER in .env):
  smtp       — SMTP via TLS (default, uses smtplib in a thread)
  sender_net — Sender.net REST API
  sendgrid   — Twilio SendGrid REST API
  mailgun    — Mailgun REST API

Each provider implements the same interface:
    async def send(to, subject, html, text="") -> bool
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool: ...


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


class SMTPProvider:
    def __init__(self, host: str, port: int, user: str, password: str, from_name: str = ""):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = f"{from_name} <{user}>" if from_name else user

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        return await asyncio.to_thread(self._send_sync, to, subject, html, text)

    def _send_sync(self, to: str, subject: str, html: str, text: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = to
            if text:
                msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._user, to, msg.as_string())
            return True
        except Exception as exc:
            logger.error("SMTP send failed to %s: %s", to, exc)
            return False


# ---------------------------------------------------------------------------
# Sender.net
# ---------------------------------------------------------------------------


class SenderNetProvider:
    _BASE = "https://api.sender.net/v2"

    def __init__(self, api_key: str, from_email: str, from_name: str = ""):
        self._key = api_key
        self._from = {"email": from_email, "name": from_name}

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        payload: dict = {
            "from": self._from,
            "to": [{"email": to}],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self._BASE}/emails",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._key}"},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Sender.net send failed to %s: %s", to, exc)
            return False


# ---------------------------------------------------------------------------
# SendGrid (Twilio)
# ---------------------------------------------------------------------------


class SendGridProvider:
    _BASE = "https://api.sendgrid.com/v3"

    def __init__(self, api_key: str, from_email: str, from_name: str = ""):
        self._key = api_key
        self._from = {"email": from_email, "name": from_name}

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        content = [{"type": "text/html", "value": html}]
        if text:
            content.insert(0, {"type": "text/plain", "value": text})
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": self._from,
            "subject": subject,
            "content": content,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self._BASE}/mail/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._key}"},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("SendGrid send failed to %s: %s", to, exc)
            return False


# ---------------------------------------------------------------------------
# Mailgun
# ---------------------------------------------------------------------------


class MailgunProvider:
    def __init__(self, api_key: str, domain: str, from_email: str, from_name: str = ""):
        self._key = api_key
        self._domain = domain
        self._from = f"{from_name} <{from_email}>" if from_name else from_email

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        data = {"from": self._from, "to": to, "subject": subject, "html": html}
        if text:
            data["text"] = text
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"https://api.mailgun.net/v3/{self._domain}/messages",
                    auth=("api", self._key),
                    data=data,
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Mailgun send failed to %s: %s", to, exc)
            return False


# ---------------------------------------------------------------------------
# Null provider (for testing / unconfigured)
# ---------------------------------------------------------------------------


class NullProvider:
    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        logger.warning("[EMAIL STUB] to=%s subject=%s (no provider configured)", to, subject)
        return True


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_provider() -> EmailProvider:
    """Build the email provider from environment / settings."""
    from utils.database.config import settings

    provider = settings.email_provider.lower()

    if provider == "sender_net":
        if not settings.email_api_key or not settings.email_from_address:
            logger.warning("Sender.net requires EMAIL_API_KEY and EMAIL_FROM_ADDRESS")
            return NullProvider()
        return SenderNetProvider(settings.email_api_key, settings.email_from_address, settings.email_from_name)

    if provider == "sendgrid":
        if not settings.email_api_key or not settings.email_from_address:
            logger.warning("SendGrid requires EMAIL_API_KEY and EMAIL_FROM_ADDRESS")
            return NullProvider()
        return SendGridProvider(settings.email_api_key, settings.email_from_address, settings.email_from_name)

    if provider == "mailgun":
        import os
        domain = os.getenv("EMAIL_MAILGUN_DOMAIN", "")
        if not settings.email_api_key or not domain or not settings.email_from_address:
            logger.warning("Mailgun requires EMAIL_API_KEY, EMAIL_MAILGUN_DOMAIN, and EMAIL_FROM_ADDRESS")
            return NullProvider()
        return MailgunProvider(settings.email_api_key, domain, settings.email_from_address, settings.email_from_name)

    # Default: SMTP
    import os
    smtp_user = settings.email_from_address or os.getenv("SENDER_EMAIL", "")
    smtp_pass = os.getenv("SENDER_PASSWORD", "") or os.getenv("EMAIL_SMTP_PASSWORD", "")
    if not smtp_user or not smtp_pass:
        logger.warning("SMTP provider requires EMAIL_FROM_ADDRESS and SENDER_PASSWORD")
        return NullProvider()
    return SMTPProvider(
        host=settings.email_smtp_server,
        port=settings.email_smtp_port,
        user=smtp_user,
        password=smtp_pass,
        from_name=settings.email_from_name,
    )


# Singleton — built lazily on first use
_provider: EmailProvider | None = None


def get_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        _provider = build_provider()
    return _provider
