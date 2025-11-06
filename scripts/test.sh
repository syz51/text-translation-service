#!/bin/bash
# Run all tests with coverage

set -e

echo "Running tests with coverage..."

# Run pytest with coverage
pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v \
    "$@"

echo "Tests completed. Coverage report generated in htmlcov/"

