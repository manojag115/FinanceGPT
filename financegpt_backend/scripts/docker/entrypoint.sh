#!/bin/bash
set -e

# Function to handle shutdown gracefully
cleanup() {
    echo "Shutting down services..."
    kill -TERM "$backend_pid" "$celery_worker_pid" "$celery_beat_pid" 2>/dev/null || true
    wait "$backend_pid" "$celery_worker_pid" "$celery_beat_pid" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Run database migrations with safeguards
echo "Running database migrations..."
# Wait for database to be ready (max 30 seconds)
for i in {1..30}; do
    if python -c "from app.db import engine; import asyncio; asyncio.run(engine.dispose())" 2>/dev/null; then
        echo "Database is ready."
        break
    fi
    echo "Waiting for database... ($i/30)"
    sleep 1
done

# Run migrations with timeout (60 seconds max)
if timeout 60 alembic upgrade head 2>&1; then
    echo "Migrations completed successfully."
    
    # Rebuild Electric publication with explicit table list (Electric SQL doesn't detect FOR ALL TABLES properly)
    echo "Updating Electric publication with explicit table list..."
    python -c "
import os
import asyncpg
import asyncio

async def update_publication():
    # Connect as electric user (who has REPLICATION and ALTER PUBLICATION privileges)
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST', 'db'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user='postgres',
        password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'financegpt')
    )
    
    try:
        # Get all user tables (exclude alembic_version and postgis tables)
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
              AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')
            ORDER BY tablename
        ''')
        
        if tables:
            table_list = ', '.join([f'public.{t[\"tablename\"]}' for t in tables])
            await conn.execute(f'DROP PUBLICATION IF EXISTS electric_publication_default')
            await conn.execute(f'CREATE PUBLICATION electric_publication_default FOR TABLE {table_list}')
            print(f'Updated publication with {len(tables)} tables')
        else:
            print('No tables found to add to publication')
    finally:
        await conn.close()

asyncio.run(update_publication())
" 2>&1 || echo "WARNING: Could not update Electric publication"
    
else
    echo "WARNING: Migration failed or timed out. Continuing anyway..."
    echo "You may need to run migrations manually: alembic upgrade head"
fi

echo "Starting FastAPI Backend..."
python main.py &
backend_pid=$!

# Wait a bit for backend to initialize
sleep 5

echo "Starting Celery Worker..."
celery -A app.celery_app worker --loglevel=info &
celery_worker_pid=$!

# Wait a bit for worker to initialize
sleep 3

echo "Starting Celery Beat..."
celery -A app.celery_app beat --loglevel=info &
celery_beat_pid=$!

echo "All services started. PIDs: Backend=$backend_pid, Worker=$celery_worker_pid, Beat=$celery_beat_pid"

# Wait for any process to exit
wait -n

# If we get here, one process exited, so exit with its status
exit $?
