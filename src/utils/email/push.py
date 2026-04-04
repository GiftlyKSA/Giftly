"""
Push notification utility stub.

To go live:
1. Add FCM server key or APNs certificate to .env / config
2. Replace the body of send_push_notification() with the real SDK call
   (Firebase Admin SDK for FCM, or httpx for APNs HTTP/2 API)
"""

import logging

logger = logging.getLogger(__name__)


async def send_push_notification(
    push_token: str, title: str, body: str, data: dict = None
) -> None:
    """
    Send a push notification to a device.

    Args:
        push_token: FCM registration token or APNs device token
        title:      Notification title
        body:       Notification body text
        data:       Optional extra key/value payload
    """
    if not push_token:
        return

    logger.info("[PUSH STUB] To: %s | %s — %s", push_token[:12] + "...", title, body)

    # TODO: replace with real provider, e.g. Firebase Admin SDK:
    # from firebase_admin import messaging
    # message = messaging.Message(
    #     notification=messaging.Notification(title=title, body=body),
    #     data=data or {},
    #     token=push_token,
    # )
    # messaging.send(message)
