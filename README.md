# Contacts API v2.1

A production-ready REST API for managing contacts, built with FastAPI, SQLAlchemy 2.0, and Pydantic v2. Features JWT authentication, email verification, password reset, role-based access control, Redis caching, rate limiting, CORS support, and Cloudinary avatar uploads.

## New in v2.1

- **Redis Caching**: User authentication data is cached in Redis to reduce database load
- **Password Reset Flow**: Email-based password reset with secure, single-use tokens
- **Role-Based Access Control**: User and Admin roles with different permissions
- **Admin-Only Avatar Upload**: Only admin users can update their avatar
- **Sphinx Documentation**: Auto-generated API documentation from docstrings
- **Improved Test Coverage**: ≥75% coverage with pytest-cov enforcement

## Features

- **Authentication**: JWT-based authentication with secure password hashing (bcrypt)
- **Email Verification**: Users must verify their email before logging in
- **Password Reset**: Secure email-based password reset flow
- **Authorization**: Per-user data isolation - each user can only access their own contacts
- **Role-Based Access**: User and Admin roles with configurable permissions
- **CRUD Operations**: Full create, read, update, delete functionality for contacts
- **Search**: Flexible search by name or email with pagination
- **Upcoming Birthdays**: Find contacts with birthdays in the next N days
- **Avatar Upload**: Profile pictures stored in Cloudinary with automatic optimization (Admin only)
- **Redis Caching**: Authenticated user data cached for performance
- **Rate Limiting**: Protected endpoints are rate-limited (Redis-backed)
- **CORS**: Configured for localhost development

## Tech Stack

- **Python** 3.11+
- **FastAPI** - Modern, fast web framework
- **SQLAlchemy 2.0** - ORM with async support
- **Pydantic v2** - Data validation
- **PostgreSQL** - Primary database
- **Redis** - Caching and rate limiting
- **Cloudinary** - Image storage
- **Mailhog** - Email testing
- **Docker & Docker Compose** - Containerization
- **Sphinx** - Documentation generation
- **pytest** - Testing with coverage enforcement

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### 1. Clone and Setup

```bash
git clone <repository-url>
cd contacts-api

# Copy environment file
cp .env.example .env

# Edit .env with your settings (especially SECRET_KEY and PASSWORD_RESET_SECRET for production!)
```

### 2. Start Services

```bash
docker-compose up --build
```

This will start:
- **API**: http://localhost:8000 (Swagger UI at /docs)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Mailhog Web UI**: http://localhost:8025 (view verification and password reset emails)

### 3. Test the API

1. Open http://localhost:8000/docs
2. Register a new user via `POST /api/auth/register`
3. Check Mailhog at http://localhost:8025 for the verification email
4. Click the verification link or use `GET /api/auth/verify?token=...`
5. Login via `POST /api/auth/login` to get JWT token
6. Use the token in Swagger UI (click "Authorize" button)
7. Create and manage contacts!

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user (201) |
| GET | `/api/auth/verify` | Verify email with token |
| POST | `/api/auth/login` | Login and get JWT token |
| POST | `/api/auth/resend-verification` | Resend verification email |
| POST | `/api/auth/request-password-reset` | Request password reset (202) |
| GET | `/api/auth/reset-password` | Validate reset token |
| POST | `/api/auth/reset-password` | Reset password with token |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get current user profile (rate-limited) |
| PATCH | `/api/users/me/avatar` | Upload avatar image (Admin only) |

### Contacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/contacts` | Create contact (201) |
| GET | `/api/contacts` | List contacts with search/pagination |
| GET | `/api/contacts/{id}` | Get contact by ID |
| PUT | `/api/contacts/{id}` | Full update contact |
| PATCH | `/api/contacts/{id}` | Partial update contact |
| DELETE | `/api/contacts/{id}` | Delete contact |
| GET | `/api/contacts/upcoming-birthdays` | Get upcoming birthdays |

## Authentication Flow

### Email Verification Policy

**Unverified users cannot obtain JWT tokens.** The flow is:

1. User registers → receives verification email
2. User clicks verification link → email marked as verified
3. User can now login and receive JWT token
4. JWT token required for all protected endpoints

### Password Reset Flow

1. User requests password reset → `POST /api/auth/request-password-reset`
2. System sends email with reset link (always returns 202 to prevent user enumeration)
3. User clicks link → validates token with `GET /api/auth/reset-password?token=...`
4. User submits new password → `POST /api/auth/reset-password`
5. User can login with new password

### JWT Token Usage

```bash
# Login to get token
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=yourpassword"

# Use token in requests
curl "http://localhost:8000/api/users/me" \
  -H "Authorization: Bearer <your_token>"
```

## Role-Based Access Control

### Roles

- **user**: Default role for new registrations. Can manage contacts and view profile.
- **admin**: Elevated permissions. Can also upload/update avatar.

### Promoting a User to Admin

Currently, admin promotion must be done directly in the database:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your-admin@example.com';
```

Or via a custom migration/script. Future versions may include an admin panel.

### Avatar Upload Policy

**Only admin users can update their avatar.** Regular users will receive a 403 Forbidden error when attempting to upload an avatar via `PATCH /api/users/me/avatar`.

## Redis Caching

### User Cache

- **Key format**: `user:{user_id}`
- **TTL**: Configurable via `USER_CACHE_TTL` (default: 900 seconds / 15 minutes)
- **Cache invalidation**: Automatic on password change, avatar update, email verification
- **Security**: Only safe fields cached (no password hashes)

### Benefits

- Reduces database load for authenticated requests
- Faster response times for `/api/users/me`
- Graceful degradation when Redis is unavailable

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://postgres:mysecretpassword@db:5432/contacts_db` |
| `SECRET_KEY` | JWT signing key (change in production!) | `your-super-secret-key...` |
| `PASSWORD_RESET_SECRET` | Password reset token signing key | `password-reset-secret...` |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Reset token lifetime | `30` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `30` |
| `USER_CACHE_TTL` | User cache TTL in seconds | `900` |
| `CORS_ORIGINS_STR` | Comma-separated allowed origins | `http://localhost:3000,...` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `ME_RATE_LIMIT` | Rate limit for /api/users/me | `5/minute` |
| `MAIL_SERVER` | SMTP server | `mailhog` |
| `MAIL_PORT` | SMTP port | `1025` |
| `CLOUDINARY_*` | Cloudinary credentials | (required for avatars) |

### Cloudinary Setup

1. Create account at https://cloudinary.com
2. Get credentials from dashboard
3. Add to `.env`:
   ```
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

## Development

### Local Setup (without Docker)

```bash
# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Set environment variables
export DATABASE_URL="postgresql+psycopg2://postgres:password@localhost:5432/contacts_db"

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Coverage is enforced at 75% minimum (configured in pyproject.toml)
# Tests will fail if coverage drops below threshold

# Run specific test file
pytest tests/test_auth.py -v

# Run tests without coverage enforcement
pytest --no-cov
```

### Building Documentation

```bash
# Install Sphinx (included in dev dependencies)
poetry install

# Build HTML documentation
cd docs
make html

# Open in browser
open _build/html/index.html
```

### Code Quality

```bash
# Format code
black app tests

# Lint
ruff check app tests

# Type check
mypy app
```

## Database Migrations

### Create new migration

```bash
alembic revision --autogenerate -m "description"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback migration

```bash
alembic downgrade -1
```

## Project Structure

```
contacts-api/
├── app/
│   ├── core/
│   │   ├── config.py      # Settings management
│   │   └── security.py    # Password hashing, JWT, reset tokens
│   ├── routers/
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── users.py       # User profile endpoints
│   │   └── contacts.py    # Contacts CRUD endpoints
│   ├── services/
│   │   ├── email.py       # Email service
│   │   ├── cloud.py       # Cloudinary service
│   │   ├── cache.py       # Redis cache helpers
│   │   └── password_reset.py  # Reset token management
│   ├── crud.py            # Database operations
│   ├── db.py              # Database session
│   ├── deps.py            # FastAPI dependencies (auth, caching)
│   ├── main.py            # Application entry point
│   ├── models.py          # SQLAlchemy models
│   └── schemas.py         # Pydantic schemas
├── alembic/
│   └── versions/          # Migration files
├── docs/
│   ├── conf.py            # Sphinx configuration
│   ├── index.rst          # Documentation index
│   ├── api.rst            # API reference
│   └── Makefile           # Build commands
├── tests/
│   ├── conftest.py        # Fixtures and test config
│   ├── test_auth.py       # Authentication tests
│   ├── test_contacts_authz.py  # Authorization tests
│   ├── test_cache_current_user.py  # Redis caching tests
│   ├── test_password_reset.py  # Password reset tests
│   └── test_roles_avatar.py  # Role enforcement tests
├── .env.example           # Environment template
├── docker-compose.yaml    # Docker services
├── Dockerfile             # API container
├── pyproject.toml         # Poetry config & dependencies
└── README.md              # This file
```

## Data Models

### User

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| email | str | Unique, indexed |
| hashed_password | str | bcrypt hash |
| full_name | str? | Optional |
| avatar_url | str? | Cloudinary URL |
| is_active | bool | Account status |
| is_verified | bool | Email verified |
| role | enum | 'user' or 'admin' |

### Contact

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| first_name | str | Indexed |
| last_name | str | Indexed |
| email | str | Globally unique |
| phone | str | Validated format |
| birthday | date | For birthday search |
| notes | str? | Optional |
| user_id | int | Foreign key to User |

**Note**: Contact emails are globally unique (not per-user) for simplicity.

## HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created (registration, contact creation) |
| 202 | Accepted (password reset request) |
| 400 | Bad request (invalid token, etc.) |
| 401 | Unauthorized (invalid/missing token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found |
| 409 | Conflict (duplicate email) |
| 422 | Validation error |
| 429 | Rate limit exceeded |

## Security Considerations

- **Secrets**: Never commit `.env` file. Use strong, unique values for `SECRET_KEY` and `PASSWORD_RESET_SECRET` in production.
- **HTTPS**: Always use HTTPS in production.
- **Password Reset**: Tokens are single-use and time-limited. Always returns 202 to prevent user enumeration.
- **Cache Security**: No sensitive data (passwords) is cached in Redis.
- **Rate Limiting**: Protects against brute force attacks on authentication endpoints.

## License

MIT License
