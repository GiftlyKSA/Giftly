from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    access_token_expire_minutes: int

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")

settings = Settings()
