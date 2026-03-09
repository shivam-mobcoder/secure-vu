#!/bin/bash
set -e

echo "Setting up PostgreSQL role..."
sudo -u postgres psql -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cctv_user') THEN CREATE ROLE cctv_user WITH LOGIN PASSWORD 'StrongPassword123'; END IF; END \$\$;"

echo "Setting up PostgreSQL database 'cctv_platform'..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'cctv_platform'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE cctv_platform;"

echo "Granting database privileges..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE cctv_platform TO cctv_user;"

echo "Setting schema owner..."
sudo -u postgres psql -d cctv_platform -c "ALTER SCHEMA public OWNER TO cctv_user;"

echo "Running migrations..."
if [ -f "migrations/001_init.sql" ]; then
    sudo -u postgres psql -d cctv_platform -f migrations/001_init.sql
else
    echo "Warning: migrations/001_init.sql not found in the current directory. Skipping migration."
fi

echo "Granting table and sequence privileges..."
sudo -u postgres psql -d cctv_platform -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cctv_user;"
sudo -u postgres psql -d cctv_platform -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cctv_user;"

echo "Database setup completed successfully!"
