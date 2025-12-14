# Contacts API v2.0

A production-ready REST API for managing contacts, built with FastAPI, SQLAlchemy 2.0, and Pydantic v2. Features JWT authentication, email verification, rate limiting, CORS support, and Cloudinary avatar uploads.

## Features

- **Authentication**: JWT-based authentication with secure password hashing (bcrypt)
- **Email Verification**: Users must verify their email before logging in
- **Authorization**: Per-user data isolation - each user can only access their own contacts
- **CRUD Operations**: Full create, read, update, delete functionality for contacts
- **Search**: Flexible search by name or email with pagination
- **Upcoming Birthdays**: Find contacts with birthdays in the next N days
- **Avatar Upload**: Profile pictures stored in Cloudinary with automatic optimization
- **Rate Limiting**: Protected endpoints are rate-limited (Redis-backed)
- **CORS**: Configured for localhost development

## Tech Stack

- **Python** 3.11+
- **FastAPI** - Modern, fast web framework
- **SQLAlchemy 2.0** - ORM with async support
- **Pydantic v2** - Data validation
- **PostgreSQL** - Primary database
- **Redis** - Rate limiting backend
- **Cloudinary** - Image storage
- **Mailhog** - Email testing
- **Docker & Docker Compose** - Containerization

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

# Edit .env with your settings (especially SECRET_KEY for production!)
```

### 2. Start Services

```bash
docker-compose up --build
```

This will start:
- **API**: http://localhost:8000 (Swagger UI at /docs)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Mailhog Web UI**: http://localhost:8025 (view verification emails)

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

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get current user profile (rate-limited) |
| PATCH | `/api/users/me/avatar` | Upload avatar image |

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

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://postgres:mysecretpassword@db:5432/contacts_db` |
| `SECRET_KEY` | JWT signing key (change in production!) | `your-super-secret-key...` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `30` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,...` |
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
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py -v
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
│   │   └── security.py    # Password hashing, JWT
│   ├── routers/
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── users.py       # User profile endpoints
│   │   └── contacts.py    # Contacts CRUD endpoints
│   ├── services/
│   │   ├── email.py       # Email service
│   │   └── cloud.py       # Cloudinary service
│   ├── crud.py            # Database operations
│   ├── db.py              # Database session
│   ├── deps.py            # FastAPI dependencies
│   ├── main.py            # Application entry point
│   ├── models.py          # SQLAlchemy models
│   └── schemas.py         # Pydantic schemas
├── alembic/
│   └── versions/          # Migration files
├── tests/
│   ├── test_auth.py       # Authentication tests
│   └── test_contacts_authz.py  # Authorization tests
├── .env.example           # Environment template
├── docker-compose.yaml    # Docker services
├── Dockerfile             # API container
├── pyproject.toml         # Poetry config & dependencies
└── poetry.lock            # Locked dependencies
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
| 400 | Bad request |
| 401 | Unauthorized (invalid/missing token) |
| 404 | Not found |
| 409 | Conflict (duplicate email) |
| 422 | Validation error |
| 429 | Rate limit exceeded |

## License

MIT License
