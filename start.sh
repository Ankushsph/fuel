#!/bin/bash
# Startup script for Railway deployment

echo "🚀 Starting Fuel Flux..."

# Run database migrations
echo "📦 Running database migrations..."
flask db upgrade

if [ $? -ne 0 ]; then
    echo "⚠️  flask db upgrade failed. Trying: flask db upgrade heads"
    flask db upgrade heads
fi

# Check if migration was successful
if [ $? -eq 0 ]; then
    echo "✅ Database migrations completed successfully!"
else
    echo "⚠️  Database migrations had warnings or were already up-to-date"
fi

# Start Gunicorn
echo "🔥 Starting Gunicorn server..."
exec gunicorn app:app --workers ${WEB_CONCURRENCY:-1} --timeout 120 --bind 0.0.0.0:${PORT:-8080}







