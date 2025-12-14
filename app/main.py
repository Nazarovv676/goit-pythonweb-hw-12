# app/main.py
"""
FastAPI application entry point with authentication, rate limiting, and CORS.

This module configures and creates the FastAPI application instance with:
- Lifespan management (startup/shutdown handlers)
- Redis connection for caching and rate limiting
- CORS middleware for cross-origin requests
- Rate limiting with slowapi
- Router registration for all API endpoints
- OpenAPI documentation (Swagger UI and ReDoc)

The application provides a REST API for managing contacts with
JWT authentication, email verification, and role-based access control.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import HTMLResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.routers import auth, contacts, users

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler for startup and shutdown events.

    On startup:
    - Logs application info
    - Initializes Redis connection for caching and rate limiting

    On shutdown:
    - Closes Redis connection
    - Logs shutdown message

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application.
    """
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Debug mode: %s", settings.debug)

    # Initialize Redis connection for caching and rate limiting
    try:
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        app.state.redis = redis_client
        logger.info("Redis connected for caching and rate limiting")
    except Exception as e:
        logger.warning(f"Redis not available, caching disabled: {e}")
        app.state.redis = None

    yield

    # Cleanup
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.close()
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="""
## Contacts API v2.1

A REST API for managing contacts with full authentication and authorization.

### Features

- **Authentication**: JWT-based authentication with email verification
- **Authorization**: Per-user data isolation - each user can only access their contacts
- **Role-Based Access**: User and Admin roles with different permissions
- **CRUD Operations**: Create, read, update, and delete contacts
- **Search**: Search contacts by name or email with flexible filtering
- **Upcoming Birthdays**: Find contacts with birthdays in the next N days
- **Avatar Upload**: Upload profile pictures to Cloudinary (Admin only)
- **Rate Limiting**: Protected endpoints are rate-limited
- **Redis Caching**: User data cached to reduce database load
- **Password Reset**: Email-based password reset flow

### Authentication Flow

1. **Register**: `POST /api/auth/register` - Creates account and sends verification email
2. **Verify Email**: Click the link in the verification email
3. **Login**: `POST /api/auth/login` - Returns JWT access token
4. **Use Token**: Include `Authorization: Bearer <token>` header in requests

### Password Reset Flow

1. **Request Reset**: `POST /api/auth/request-password-reset` - Sends reset email
2. **Reset Password**: `POST /api/auth/reset-password` - Sets new password with token

### Role-Based Access Control

- **User Role**: Standard permissions for contact management
- **Admin Role**: Can update avatar (in addition to user permissions)

### Email Verification Policy

**Unverified users cannot obtain JWT tokens.** Users must verify their email before logging in.

### Search Behavior

- Use `q` parameter for general search (OR semantics across first_name, last_name, email)
- Use individual field parameters for precise filtering (AND semantics)
- All searches are case-insensitive partial matches

### Rate Limits

- `/api/users/me`: 5 requests per minute per IP
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

# Add rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/redoc", include_in_schema=False)
def redoc_html() -> HTMLResponse:
    """
    Custom ReDoc page with stable version.

    Returns:
        HTML response with ReDoc documentation.
    """
    return get_redoc_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """
    Redirect root to API documentation.

    Returns:
        Redirect response to /docs.
    """
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns service status and version for monitoring.

    Returns:
        Dictionary with status and version.
    """
    return {"status": "healthy", "version": settings.app_version}
