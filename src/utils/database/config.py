import os
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str
    database_url: str
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=60, ge=1, le=365)
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket_name: str
    aws_region: str = "auto"  # Default to auto if not specified
    storage_endpoint_url: str = ""  # Optional Cloudflare R2 endpoint

    # OTP settings
    otp_expiry_seconds: int = 90  # How long an OTP is valid
    rate_limit_otp_max: int = 3  # Max OTP requests per phone per window
    rate_limit_otp_window_seconds: int = 600  # Rate-limit window (10 minutes)

    # SMS provider (set sms_provider_enabled=True and implement utils/sms.py to go live)
    sms_provider_enabled: bool = False

    # Redis — used as the TaskIQ message broker for background email tasks
    redis_url: str = "redis://localhost:6379"

    # Dev mode — exposes /auth/dev/otp for testing without an SMS provider
    debug: bool = False

    # Paylink.sa payment gateway
    paylink_api_id: str = ""          # apiId for Bearer-token auth (recommended)
    paylink_api_key: str = ""         # secretKey (or legacy X-API-KEY when api_id is empty)
    paylink_test_mode: bool = True
    paylink_callback_url: str = ""
    paylink_return_url: str = ""
    paylink_callback_rate_limit_per_minute: int = 10

    # Email provider: smtp | sender_net | sendgrid | mailgun
    email_provider: str = "smtp"
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_from_address: str = ""
    email_from_name: str = "Giftly"
    email_api_key: str = ""   # API key for HTTP-based providers

    # Chat message limits
    chat_msg_max_chars: int = 300
    chat_image_max_bytes: int = 6 * 1024 * 1024   # 6 MB
    chat_video_max_bytes: int = 70 * 1024 * 1024  # 70 MB
    chat_video_max_secs: int = 30

    # Wallet charge limits (SAR)
    wallet_charge_min_sar: int = 10
    wallet_charge_max_sar: int = 1000

    # Paylink webhook secret — if set, HMAC-SHA256 of the raw JSON body must match X-Paylink-Signature
    paylink_webhook_secret: str = ""

    # Per-endpoint rate limits (requests per minute per IP)
    rate_limit_payment_create_per_minute: int = 20
    rate_limit_wallet_charge_per_minute: int = 5
    rate_limit_coupon_verify_per_minute: int = 10

    # WebSocket per-user message rate limit (messages per minute)
    ws_msg_rate_limit_per_minute: int = 60

    # Temporary access token lifetime for new unverified customers (minutes)
    temp_token_expire_minutes: int = 30

    # Maximum invoice amount (SAR) — courier-created invoices are capped at this value
    invoice_max_amount_sar: int = 50_000

    # Conversations list page size cap
    chat_conversations_max_limit: int = 100

    # Admin wallet charge limit (halalas; 1 SAR = 100 halalas)
    admin_wallet_charge_max_halalas: int = 1_000_000

    # WebSocket max raw payload size (bytes)
    ws_max_payload_bytes: int = 65_536  # 64 KB

    # Security headers
    hsts_max_age_seconds: int = 31536000

    # Storage base URL for public asset CDN (Cloudflare R2 / S3)
    storage_base_url: str = "https://storage-giftly-storage.cranl.net"

    # CORS allowed origins — comma-separated list or JSON array in .env
    allowed_origins: list[str] = ["*"]

    # Task broker — set to False to use in-memory broker when Redis is unavailable (dev/CI)
    use_redis_broker: bool = True

    def model_post_init(self, __context) -> None:
        # Validate secret_key strength
        if len(self.secret_key) < 32:
            raise ValueError("secret_key must be at least 32 characters long")
        if not re.search(r"[A-Z]", self.secret_key):
            raise ValueError("secret_key must contain at least one uppercase letter")
        if not re.search(r"[a-z]", self.secret_key):
            raise ValueError("secret_key must contain at least one lowercase letter")
        if not re.search(r"[0-9]", self.secret_key):
            raise ValueError("secret_key must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', self.secret_key):
            raise ValueError("secret_key must contain at least one special character")

        # Validate required environment variables are set
        required_env_vars = [
            "secret_key",
            "database_url",
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_s3_bucket_name",
            "redis_url",
        ]

        for var_name in required_env_vars:
            value = getattr(self, var_name)
            if not value or (isinstance(value, str) and not value.strip()):
                raise ValueError(
                    f"Environment variable {var_name} is required but not set"
                )

    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(__file__), ".env"))


settings = Settings()
