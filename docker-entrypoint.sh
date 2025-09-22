#!/bin/sh
set -e

# Wait for the database to be ready
echo "Waiting for database to be ready..."
python -c "
import time
import psycopg2
import os

host = os.environ.get('DB_HOST', 'db')
port = os.environ.get('DB_PORT', '5432')
user = os.environ.get('DB_USER', 'postgres')
password = os.environ.get('DB_PASSWORD', 'postgres')
dbname = os.environ.get('DB_NAME', 'fastapi_firebase')

while True:
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        conn.close()
        break
    except psycopg2.OperationalError:
        print('Database not ready yet. Waiting...')
        time.sleep(1)
"

echo "Database is ready!"

# Run database migrations using Alembic
echo "Running database migrations..."
alembic upgrade head

# Initialize database if needed
echo "Initializing database if needed..."
python -m app.init_db

# Start the application
echo "Starting application..."
exec "$@" 