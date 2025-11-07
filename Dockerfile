FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
	--mount=type=bind,source=uv.lock,target=uv.lock \
	--mount=type=bind,source=pyproject.toml,target=pyproject.toml \
	uv sync --locked --no-install-project --no-dev

# Copy project files
COPY ./pyproject.toml /app/pyproject.toml
COPY ./uv.lock /app/uv.lock

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
	uv sync --locked --no-dev


FROM python:3.13-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Create app user
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /bin/bash --create-home app
USER app

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app /app

# Copy application code
COPY --chown=app:app ./app /app/app

# Copy alembic files for migrations
COPY --chown=app:app ./alembic.ini /app/alembic.ini
COPY --chown=app:app ./alembic /app/alembic

WORKDIR /app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
	CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health', timeout=5.0)"

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
