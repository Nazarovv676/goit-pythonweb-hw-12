# app/services/email.py
"""
Email service for sending verification and notification emails.

This module provides async email sending functionality using fastapi-mail.
Supports HTML email templates for:
- Email verification during registration
- Password reset requests

Email configuration is loaded from application settings and supports
both development (Mailhog) and production (real SMTP) modes.
"""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=settings.mail_tls,
    MAIL_SSL_TLS=settings.mail_ssl,
    USE_CREDENTIALS=bool(settings.mail_username and settings.mail_password),
    VALIDATE_CERTS=False,
)


async def send_verification_email(email: str, base_url: str) -> None:
    """
    Send an email verification link to the user.

    Generates a verification token and sends an HTML email with
    a clickable verification link.

    Args:
        email: The user's email address.
        base_url: The base URL of the application (e.g., http://localhost:8000).

    Raises:
        Exception: If email sending fails (logged and re-raised).

    Note:
        In debug mode, the verification URL is also logged for convenience.
    """
    from app.core.security import create_email_verification_token

    token = create_email_verification_token(email)
    verification_url = f"{base_url}/api/auth/verify?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Verify Your Email</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 8px 8px 0 0;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 8px 8px;
            }}
            .button {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Contacts API</h1>
        </div>
        <div class="content">
            <h2>Verify Your Email Address</h2>
            <p>Thank you for registering! Please click the button below to verify your email address:</p>
            <p style="text-align: center;">
                <a href="{verification_url}" class="button">Verify Email</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; background: #fff; padding: 10px; border-radius: 4px;">
                {verification_url}
            </p>
            <p>This link will expire in {settings.verification_token_expire_hours} hours.</p>
            <p>If you didn't create an account, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2024 Contacts API. All rights reserved.</p>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Verify Your Email - Contacts API",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)

    try:
        await fm.send_message(message)
        logger.info(f"Verification email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        # In development, log the verification URL for debugging
        if settings.debug:
            logger.info(f"Verification URL: {verification_url}")
        raise


async def send_password_reset_email(
    email: str, reset_token: str, base_url: str
) -> None:
    """
    Send a password reset link to the user.

    Generates an HTML email with a clickable password reset link.
    The reset token is included as a query parameter.

    Args:
        email: The user's email address.
        reset_token: The password reset token generated by security module.
        base_url: The base URL of the application.

    Raises:
        Exception: If email sending fails (logged and re-raised).

    Note:
        In debug mode, the reset URL is also logged for convenience.
    """
    reset_url = f"{base_url}/api/auth/reset-password?token={reset_token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Reset Your Password</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 8px 8px 0 0;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 8px 8px;
            }}
            .button {{
                display: inline-block;
                background: #e74c3c;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .warning {{
                background: #fff3cd;
                border: 1px solid #ffc107;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Contacts API</h1>
        </div>
        <div class="content">
            <h2>Reset Your Password</h2>
            <p>We received a request to reset your password. Click the button below to set a new password:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">Reset Password</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; background: #fff; padding: 10px; border-radius: 4px;">
                {reset_url}
            </p>
            <div class="warning">
                <strong>⚠️ Security Notice:</strong>
                <ul>
                    <li>This link will expire in {settings.password_reset_expire_minutes} minutes.</li>
                    <li>This link can only be used once.</li>
                    <li>If you didn't request a password reset, please ignore this email or contact support if you're concerned.</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p>© 2024 Contacts API. All rights reserved.</p>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Reset Your Password - Contacts API",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)

    try:
        await fm.send_message(message)
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        # In development, log the reset URL for debugging
        if settings.debug:
            logger.info(f"Password reset URL: {reset_url}")
        raise
