"""
Email utilities — thin wrapper around the configured email provider.

Use `send_email_with_template` (async) to send templated emails.
Provider is selected via EMAIL_PROVIDER env var (see providers.py).
"""

import logging
from typing import Any, Dict, Optional

from .providers import get_provider
from . import templates

logger = logging.getLogger(__name__)


async def send_email_with_template(
    to_email: str,
    subject: str,
    template_name: str,
    template_vars: Dict[str, Any],
) -> bool:
    """Render a named template and send it via the configured email provider."""
    template_content = getattr(templates, template_name, None)
    if not template_content:
        logger.error("Email template '%s' not found", template_name)
        return False

    from jinja2 import Template

    html_src = template_content.get("html", "")
    text_src = template_content.get("text", "")
    html = Template(html_src).render(**template_vars) if html_src else ""
    text = Template(text_src).render(**template_vars) if text_src else ""

    if not html and not text:
        logger.error("Email template '%s' has no html or text content", template_name)
        return False

    return await get_provider().send(to=to_email, subject=subject, html=html, text=text)


async def send_raw_email(
    to_email: str,
    subject: str,
    html: str,
    text: str = "",
) -> bool:
    """Send a raw email without template rendering."""
    return await get_provider().send(to=to_email, subject=subject, html=html, text=text)
