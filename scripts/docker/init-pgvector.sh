#!/bin/sh
# ============================================================================
# pgvector Extension Initialization Script
# ============================================================================
# This script creates the pgvector extension in the database.
# It's automatically executed by PostgreSQL on first container initialization.
# ============================================================================

set -e

echo "Creating pgvector extension in database: $POSTGRES_DB"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "pgvector extension created successfully"
