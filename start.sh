#!/bin/bash
# start.sh - Startup script for production deployment
# Runs database migrations before starting the server

set -e

echo "========================================"
echo "  Contacts API - Starting..."
echo "========================================"

# Wait for database to be ready (with timeout)
echo "Waiting for database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "from app.db import engine; engine.connect()" 2>/dev/null; then
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
echo "Running database migrations..."
python -m alembic upgrade head

echo "Migrations complete!"

# Start the server
echo "Starting uvicorn server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

