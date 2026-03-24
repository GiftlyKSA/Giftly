from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket_name: str
    aws_region: str = "auto"  # Default to auto if not specified
    storage_endpoint_url: str = ""  # Optional Cloudflare R2 endpoint

    # OTP settings
    otp_expiry_seconds: int = 90          # How long an OTP is valid
    rate_limit_otp_max: int = 3           # Max OTP requests per phone per window
    rate_limit_otp_window_seconds: int = 600  # Rate-limit window (10 minutes)

    # SMS provider (set sms_provider_enabled=True and implement utils/sms.py to go live)
    sms_provider_enabled: bool = False

    # Redis — used as the TaskIQ message broker for background email tasks
    redis_url: str = "redis://localhost:6379"

    # Dev mode — exposes /auth/dev/otp for testing without an SMS provider
    debug: bool = False

    # Paylink.sa payment gateway
    paylink_api_key: str = ""
    paylink_test_mode: bool = True
    paylink_callback_url: str = ""
    paylink_return_url: str = ""

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")

settings = Settings()
