# app/core/config.py
"""
Application configuration management.

This module provides centralized settings management using Pydantic's
BaseSettings. All configuration is loaded from environment variables
with sensible defaults for development.

Attributes:
    Settings: Main configuration class with all application settings.
    get_settings: Factory function returning cached settings instance.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    Settings are organized into logical groups: Database, Application,
    Security, CORS, Mail, Redis, Rate Limiting, and Cloudinary.

    Attributes:
        database_url: PostgreSQL connection string.
        db_echo: Enable SQLAlchemy query logging.
        app_name: Display name of the application.
        app_version: Current version string.
        debug: Enable debug mode.
        secret_key: JWT signing key (change in production!).
        algorithm: JWT algorithm (default: HS256).
        access_token_expire_minutes: JWT token lifetime in minutes.
        verification_token_expire_hours: Email verification token lifetime.
        password_reset_secret: Separate secret for password reset tokens.
        password_reset_expire_minutes: Password reset token lifetime.
        user_cache_ttl: TTL in seconds for user cache in Redis.
        cors_origins_str: Comma-separated allowed CORS origins.
        mail_*: Email/SMTP configuration settings.
        redis_url: Redis connection string.
        me_rate_limit: Rate limit for /api/users/me endpoint.
        cloudinary_*: Cloudinary service credentials.
    """

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
    app_version: str = "2.1.0"
    debug: bool = False

    # Security - JWT Access Tokens
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    verification_token_expire_hours: int = 24

    # Security - Password Reset
    password_reset_secret: str = "password-reset-secret-change-in-production"
    password_reset_expire_minutes: int = 30

    # User Cache TTL (seconds)
    user_cache_ttl: int = 900  # 15 minutes

    # CORS - stored as string internally, parsed to list
    cors_origins_str: str = (
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
    )

    @property
    def cors_origins(self) -> list[str]:
        """
        Parse CORS origins from comma-separated string.

        Returns:
            List of allowed origin URLs.
        """
        return [
            origin.strip()
            for origin in self.cors_origins_str.split(",")
            if origin.strip()
        ]

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
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are only loaded once from
    environment variables during the application lifecycle.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
