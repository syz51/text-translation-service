#!/bin/bash
# Lint code with ruff

set -e

echo "Linting code..."

# Check with ruff
ruff check app/ tests/

echo "Linting completed"

