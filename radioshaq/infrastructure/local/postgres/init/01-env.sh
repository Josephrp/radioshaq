#!/bin/bash
# Optional: set locale for PostgreSQL (PostGIS image already has PostGIS installed)
# Migrations will run: CREATE EXTENSION IF NOT EXISTS postgis;
set -e
echo "PostgreSQL init: radioshaq database will be created by Docker with user radioshaq."
