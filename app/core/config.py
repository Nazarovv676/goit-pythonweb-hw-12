# app/core/config.py
"""Application configuration management."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = (
        "postgresql+psycopg2://postgres:mysecretpassword@localhost:5432/contacts_db"
    )
    db_echo: bool = False

    # Application
    app_name: str = "Contacts API"
    app_version: str = "2.0.0"
    debug: bool = False

    # Security
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    verification_token_expire_hours: int = 24

    # CORS - stored as string internally, parsed to list
    cors_origins_str: str = "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # Mail settings
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@example.com"
    mail_port: int = 1025
    mail_server: str = "mailhog"
    mail_tls: bool = False
    mail_ssl: bool = False
    mail_from_name: str = "Contacts API"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Rate limiting
    me_rate_limit: str = "5/minute"

    # Cloudinary
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
