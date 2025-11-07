# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Production-grade FastAPI service for translating SRT subtitle files using Google GenAI's Gemini 2.5 Pro model, with transcription API capabilities. The service uses async/await throughout, SQLAlchemy 2.0 with async support, S3 for storage, and follows modern Python best practices.

## Development Commands

### Environment Setup

```bash
# Install dependencies (requires Python 3.13+)
uv sync

# Install with dev dependencies
uv sync --all-extras

# Copy environment template
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY (get from https://aistudio.google.com/apikey)
```

### Running the Service

```bash
# Development mode (local with auto-reload)
uv run uvicorn app.main:app --reload

# Development mode (Docker)
docker build -t text-translation-service .
docker run -p 8000:8000 --env-file .env text-translation-service

# Production mode (Docker)
docker build -t text-translation-service .
docker run -d -p 8000:8000 --env-file .env text-translation-service

# Production mode (local)
python -m app.main
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_api.py

# Run specific test
uv run pytest tests/test_api.py::test_translate_srt_success
```

### Code Quality

```bash
# Format code (Black + Ruff)
black app/ tests/
ruff check app/ tests/ --fix

# Lint code
ruff check app/ tests/
```

### Database Migrations

```bash
# Migrations run automatically on startup, but you can manage them manually:

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Architecture Overview

### Core Design Patterns

1. **Factory Pattern**: App creation in `app/main.py` via `create_app()` factory
2. **Dependency Injection**: FastAPI's DI system for database sessions, config, and services
3. **Middleware Stack**: CORS → GZip → TrustedHost → Authentication (in that order)
4. **Lifespan Management**: Async context manager in `main.py` handles startup/shutdown (migrations, S3 initialization)
5. **Settings Management**: Pydantic Settings with environment variables (see `app/core/config.py`)

### Translation Service Architecture

The translation service uses a sophisticated chunking strategy for better context and quality:

- **Contextual Chunking** (`app/services/translation.py`): Groups consecutive SRT entries together (default: 100 entries per chunk)
- **Multi-step Reasoning**: Uses Gemini's extended thinking mode with structured prompts (6-step process)
- **Concurrent Processing**: Uses `asyncio.Semaphore` to limit concurrent API calls (default: 25)
- **Delimiter-based Parsing**: Uses unique session IDs in delimiters to parse multi-entry responses
- **Localization Support**: Optional `country` parameter for cultural adaptation

Key files:

- `app/services/translation.py`: Core translation logic with chunking and extended thinking
- `app/services/srt_parser.py`: SRT parsing/reconstruction utilities
- `app/api/v1/translation.py`: Translation endpoint

### Transcription Service Architecture

The transcription service integrates with AssemblyAI for audio-to-SRT conversion:

- **Async Workflow**: Upload → DB record → S3 storage → AssemblyAI → Webhook → Background processing
- **Webhook Pattern**: AssemblyAI sends completion notification to `/webhooks/assemblyai/{secret_token}`
- **Polling Fallback**: Background polling recovers jobs if webhooks fail (configurable interval/threshold)
- **Background Tasks**: Transcription processing happens in background to return 200 OK within 10s
- **Presigned URLs**: S3 presigned URLs for audio upload (24h expiry) and SRT download (1h expiry)
- **Retry Logic**: Exponential backoff with configurable retry attempts
- **Concurrent Job Limits**: Enforced at API level (default: 10 concurrent jobs)

Key files:

- `app/api/v1/transcription.py`: Transcription endpoints and webhook handler
- `app/services/assemblyai_client.py`: AssemblyAI API client wrapper
- `app/services/transcription_service.py`: Transcription processing logic (idempotent)
- `app/services/polling_service.py`: Background polling for stale job recovery
- `app/db/models.py`: Job status tracking (QUEUED → PROCESSING → COMPLETED/ERROR)
- `app/storage/s3.py`: S3 wrapper with connection pooling

**Important**: The transcription API requires S3 configuration and webhook setup. The service initializes S3 client during startup but allows the app to start even if S3 fails.

**Webhook + Polling Strategy**: Webhooks provide low latency, polling ensures reliability. Jobs stuck in `processing` beyond threshold (default: 2h) are auto-recovered.

### Database Layer

- **Async SQLAlchemy 2.0**: Uses modern mapped columns and async sessions
- **CRUD Operations**: Centralized in `app/db/crud.py` (get_job, create_job, update_job_status, etc.)
- **Session Management**: Async context manager via `get_db()` dependency
- **Migrations**: Alembic with auto-generation support (see `alembic/versions/`)

### Storage Layer

- **S3 Wrapper** (`app/storage/s3.py`): Production-grade S3 client with:
  - Connection pooling (configurable via `S3_MAX_POOL_CONNECTIONS`)
  - Long-lived client initialized at startup, closed at shutdown
  - Adaptive retries (max 3 attempts)
  - Methods: `upload_audio()`, `upload_srt()`, `generate_presigned_url()`
  - Must call `initialize()` before use, `close()` on shutdown

### Authentication

- **Optional API Key**: Set `API_KEY` in `.env` to enable X-API-Key header validation
- **Security Middleware**: `app/core/security.py` handles authentication if configured
- **Constant-time Comparison**: Webhook secret validation uses `secrets.compare_digest()` to prevent timing attacks

### API Versioning

All endpoints are prefixed with `/api/v1/`:

- `/api/v1/health` - Health check
- `/api/v1/translate` - Translation endpoint
- `/api/v1/transcriptions` - Transcription job creation
- `/api/v1/transcriptions/{job_id}` - Job status
- `/api/v1/transcriptions/{job_id}/srt` - SRT download (302 redirect to S3)
- `/api/v1/webhooks/assemblyai/{secret_token}` - AssemblyAI webhook

## Important Conventions

### Error Handling

- **Translation Service**: Raises `GoogleGenAIError` for API errors (caught as 502 Bad Gateway)
- **Validation Errors**: Raises `ValueError` for SRT parsing errors (caught as 400 Bad Request)
- **Transcription Service**: Returns appropriate status codes:
  - 400: Invalid format, SRT not ready
  - 404: Job not found
  - 413: File too large
  - 429: Concurrent job limit reached
  - 500: Server errors

### Logging

- Structured logging via `app/core/logging.py`
- Log levels configurable via `LOG_LEVEL` env var
- Key events logged: chunk progress, S3 operations, job state changes, webhook events

**Log Security** (`app/core/log_filter.py`):

- `SensitiveDataFilter` automatically redacts sensitive data from all logs
- Configurable via `ENABLE_LOG_REDACTION` (default: true)
- Redacts: API keys, tokens, S3 URLs, webhook secrets, passwords
- Uses regex patterns to detect and replace sensitive data with `[REDACTED]`
- Applied to all log records before emission

### Testing Patterns

**Test Organization**:

- 213 tests across 20 test files organized by component
- Tests mirror app structure: `tests/api/`, `tests/services/`, `tests/core/`, etc.
- See `tests/README.md` for comprehensive testing guide

**Test Fixtures** (`tests/conftest.py`):

_FastAPI Test Clients:_

- `client`: Test client without auth
- `client_with_auth`: Test client with API key

_Translation Fixtures:_

- `mock_genai_client`: Mock Google GenAI client
- `create_genai_response()`: Helper to create mock API responses

_Transcription Fixtures:_

- `fake_assemblyai_client`: Test double for AssemblyAI API (returns predictable responses)
- `fake_s3_storage`: Test double for S3 operations (in-memory storage)
- `mock_transcription_services`: Mocked transcription service dependencies

_Database Fixtures:_

- `db_session`: Async database session for tests
- `init_test_db`: Initialize test database schema

_Test Doubles Pattern_:

- `FakeAssemblyAIClient`: In-memory implementation of AssemblyAI client
- `FakeS3Storage`: In-memory implementation of S3 storage
- Provides predictable behavior without external dependencies

**Important**: When mocking, patch where the function is IMPORTED, not where it's DEFINED (see `get_mock_target()` helper).

### Configuration

All configuration via environment variables (see `.env.example`):

- **Required**: `GOOGLE_API_KEY`
- **Optional Database**: `DATABASE_PATH` (default: ./data/transcriptions.db)
- **Optional S3**: `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, etc.
- **Optional Transcription**: `ASSEMBLYAI_API_KEY`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET_TOKEN`
- **Optional Polling**: `POLLING_ENABLED` (default: true), `POLLING_INTERVAL` (default: 300s), `STALE_JOB_THRESHOLD` (default: 7200s)
- **Optional Server**: `HOST`, `PORT`, `ENVIRONMENT`, `ALLOWED_HOSTS`
- **Optional Auth**: `API_KEY` (enables authentication if set)

### Settings Management & Dependency Injection

**Pattern**: Uses FastAPI's recommended DI pattern with `@lru_cache` for singleton settings (`app/core/config.py`).

**In Endpoints** (use FastAPI's `Depends`):
```python
from typing import Annotated
from fastapi import Depends
from app.core.config import Settings, get_settings

async def my_endpoint(
    settings: Annotated[Settings, Depends(get_settings)]
):
    # Use settings.google_api_key, etc.
```

**In Services** (two patterns):
1. **Accept optional settings param** (better testability):
   ```python
   def my_service_function(settings: Settings | None = None):
       if settings is None:
           settings = get_settings()
       # Use settings...
   ```

2. **Call get_settings() directly** (simpler):
   ```python
   from app.core.config import get_settings

   def my_service_function():
       settings = get_settings()
       # Use settings...
   ```

**In Tests**:
```python
from app.core.config import Settings

# Create test settings instance
test_settings = Settings(google_api_key="test_key", ...)

# Pass to functions that accept optional settings
result = await my_service(settings=test_settings)
```

**Backward Compatibility**: Module-level `settings` object still available via `from app.core.config import settings`, but new code should use `get_settings()`.

**Important**: `@lru_cache(maxsize=1)` ensures singleton pattern - only one Settings instance created per process.

## Common Pitfalls

1. **S3 Client Not Initialized**: Always ensure `s3_storage.initialize()` is called before S3 operations. The app handles this in the lifespan manager.

2. **Database Sessions**: Use `Depends(get_db)` for request handlers. Background tasks must create their own sessions via `SessionLocal()` context manager.

3. **Translation Chunking**: The service groups consecutive SRT entries for better context. Don't split entries individually unless there's a specific reason.

4. **Webhook Response Time**: Webhook handlers MUST return 200 OK within 10 seconds. Process work in background tasks.

5. **Presigned URL Expiry**: Audio URLs expire in 24h (for AssemblyAI processing), SRT URLs expire in 1h (for downloads).

6. **Job Status Race Conditions**: Update job status to PROCESSING BEFORE starting AssemblyAI to prevent webhook race conditions.

7. **Polling Service**: `process_completed_transcription()` is idempotent - safe to call multiple times (checks job status first). Polling recovers stale jobs automatically.

## Project Structure

```
app/
├── api/v1/          # API endpoints (health, translation, transcription)
├── core/            # Config, logging, log_filter (security), middleware, security
├── db/              # Database models, CRUD, session management
├── models/          # Data models (SRT entries)
├── schemas/         # Pydantic request/response models
├── services/        # Business logic (translation, transcription, polling, parsing)
└── storage/         # S3 wrapper with connection pooling
```
