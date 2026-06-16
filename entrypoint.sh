#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL to be ready..."
while ! python -c "
import socket, sys, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect((os.environ.get('DB_HOST', 'db'), int(os.environ.get('DB_PORT', '5432'))))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    echo "   PostgreSQL is unavailable — sleeping 1s..."
    sleep 1
done
echo "✅ PostgreSQL is ready!"

echo "📦 Running database migrations..."
python manage.py migrate --noinput

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

# Create superuser from env vars (skip if already exists)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    echo "👤 Creating superuser (if not exists)..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "   Superuser already exists, skipping."
fi

echo "🚀 Starting server..."
exec "$@"
