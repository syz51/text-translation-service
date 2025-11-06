#!/bin/bash
# Pre-start script for production deployments
# Run any necessary setup before starting the application

set -e

echo "Running pre-start checks..."

# Check if required environment variables are set
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "ERROR: GOOGLE_API_KEY environment variable is not set"
    exit 1
fi

echo "Environment check passed"

# Run database migrations if using Alembic (uncomment when needed)
# echo "Running database migrations..."
# alembic upgrade head

echo "Pre-start completed successfully"

