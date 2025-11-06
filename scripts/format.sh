#!/bin/bash
# Format code with black and ruff

set -e

echo "Formatting code..."

# Format with black
echo "Running black..."
black app/ tests/

# Sort imports and fix with ruff
echo "Running ruff..."
ruff check app/ tests/ --fix

echo "Code formatting completed"

