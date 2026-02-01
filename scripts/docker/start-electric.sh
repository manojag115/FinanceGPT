#!/bin/bash
# Electric SQL startup wrapper
# Waits for backend to be healthy before starting Electric
# This ensures all database migrations are complete

set -e

BACKEND_URL="${BACKEND_HEALTH_URL:-http://localhost:8000/docs}"
MAX_RETRIES=60
RETRY_INTERVAL=5

echo "⏳ Waiting for backend to be healthy..."

for i in $(seq 1 $MAX_RETRIES); do
    # Check if backend responds (any 2xx status)
    if curl -sf "$BACKEND_URL" > /dev/null 2>&1; then
        echo "✅ Backend is healthy, starting Electric SQL..."
        exec /app/electric-release/bin/entrypoint start
    fi
    echo "  Attempt $i/$MAX_RETRIES: Backend not ready, waiting ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

echo "❌ Backend failed to become healthy after $MAX_RETRIES attempts"
exit 1
