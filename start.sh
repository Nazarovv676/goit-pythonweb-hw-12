#!/bin/bash
# start.sh - Startup script for production deployment
# Runs database migrations before starting the server

set -e

echo "========================================"
echo "  Contacts API - Starting..."
echo "========================================"
echo "DATABASE_URL is set: ${DATABASE_URL:+yes}"
echo "REDIS_URL is set: ${REDIS_URL:+yes}"
echo "PORT: ${PORT:-8000}"

# Wait for database to be ready (with timeout)
echo ""
echo "Waiting for database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "
from sqlalchemy import create_engine, text
import os

url = os.environ.get('DATABASE_URL', '')
# Handle Render's postgres:// format
if url.startswith('postgres://'):
    url = url.replace('postgres://', 'postgresql+psycopg2://', 1)
elif url.startswith('postgresql://') and '+psycopg2' not in url:
    url = url.replace('postgresql://', 'postgresql+psycopg2://', 1)

engine = create_engine(url)
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('OK')
" 2>&1; then
        echo "Database connection successful!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for database... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Could not connect to database after $MAX_RETRIES attempts"
    exit 1
fi

# Run database migrations
echo ""
echo "Running database migrations..."
python -m alembic upgrade head

if [ $? -eq 0 ]; then
    echo "Migrations complete!"
else
    echo "ERROR: Migrations failed!"
    exit 1
fi

# Start the server
echo ""
echo "Starting uvicorn server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
