# Text Translation Service

Production-grade FastAPI service for translating SRT subtitle files using Google GenAI's Gemini 2.5 Pro model, with production-ready transcription API for audio-to-SRT conversion.

## Features

### Translation Service

- **SRT Format Support**: Preserves timestamps and structure
- **Enhanced Translation**: Multi-step reasoning with extended thinking for subtitle-optimized translations
- **Localization Support**: Optional country/region parameter for cultural adaptation
- **Contextual Chunking**: Groups consecutive entries for better translation context and quality
- **Concurrent Processing**: Handles multiple chunks simultaneously for speed
- **Google GenAI Integration**: Uses Gemini 2.5 Pro with extended thinking

### Transcription Service

- **Audio-to-SRT Conversion**: AssemblyAI integration for high-quality transcription
- **Webhook + Polling Hybrid**: Low-latency webhooks with fallback polling for reliability
- **S3 Storage**: Presigned URLs for secure audio upload and SRT download
- **Background Processing**: Async job processing with status tracking
- **Automatic Recovery**: Polling service recovers stale jobs if webhooks fail
- **Concurrent Job Limits**: Configurable limits to prevent resource exhaustion

### Infrastructure

- **Database Layer**: SQLAlchemy 2.0 with async support and Alembic migrations
- **S3 Storage**: Production-grade S3 wrapper with connection pooling for audio/SRT files
- **API Key Authentication**: Optional authentication layer
- **Log Security**: Automatic redaction of sensitive data (API keys, tokens, S3 URLs)
- **Background Polling**: Configurable polling for stale job recovery
- **Health Checks**: Component status monitoring (database, S3, services)
- **Auto Documentation**: Interactive API docs at `/docs`
- **Production Ready**: Proper project structure, logging, config management, CORS, middleware, and tests
- **API Versioning**: Clean v1 API structure with room for future versions

## Project Structure

```
text-translation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app factory
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/                      # API v1 routes
│   │       ├── __init__.py
│   │       ├── health.py            # Health check endpoints
│   │       ├── transcription.py     # Transcription endpoints + webhooks
│   │       └── translation.py       # Translation endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Settings management
│   │   ├── log_filter.py            # Sensitive data redaction
│   │   ├── logging.py               # Logging setup
│   │   ├── middleware.py            # Middleware configuration
│   │   └── security.py              # Auth middleware
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                  # SQLAlchemy setup
│   │   ├── crud.py                  # Database operations
│   │   └── models.py                # Database models
│   ├── models/
│   │   ├── __init__.py
│   │   └── srt.py                   # SRT data models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── transcription.py         # Transcription schemas
│   │   └── translation.py           # Translation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── assemblyai_client.py     # AssemblyAI API wrapper
│   │   ├── polling_service.py       # Background job recovery
│   │   ├── srt_parser.py            # SRT parsing logic
│   │   ├── transcription_service.py # Transcription processing
│   │   └── translation.py           # Translation service
│   └── storage/
│       ├── __init__.py
│       └── s3.py                    # S3 storage wrapper
├── alembic/
│   ├── versions/               # Database migrations
│   ├── env.py                  # Alembic environment
│   └── script.py.mako          # Migration template
├── alembic.ini                 # Alembic configuration
├── data/
│   └── transcriptions.db       # SQLite database
├── scripts/
│   ├── prestart.sh             # Pre-deployment checks
│   ├── test.sh                 # Run tests with coverage
│   ├── format.sh               # Code formatting
│   └── lint.sh                 # Code linting
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # Shared test fixtures
│   ├── README.md                          # Testing guide
│   ├── api/
│   │   └── v1/
│   │       ├── test_health.py             # Health endpoint tests
│   │       ├── test_transcription.py      # Transcription API tests
│   │       └── test_translation.py        # Translation API tests
│   ├── core/
│   │   ├── test_config.py                 # Config tests
│   │   ├── test_log_filter.py             # Log redaction tests
│   │   └── test_security.py               # Auth middleware tests
│   ├── db/
│   │   ├── test_crud.py                   # CRUD tests
│   │   └── test_models.py                 # Model tests
│   ├── services/
│   │   ├── test_assemblyai_client.py      # AssemblyAI client tests
│   │   ├── test_polling_service.py        # Polling service tests
│   │   ├── test_srt_parser.py             # Parser tests
│   │   ├── test_transcription_service.py  # Transcription logic tests
│   │   └── test_translation.py            # Translation logic tests
│   └── storage/
│       └── test_s3.py                     # S3 storage tests
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker (optional)

### Installation

1. **Clone and install dependencies:**

   Using uv (recommended):

   ```bash
   uv sync
   ```

   Using pip:

   ```bash
   pip install -e .
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your Google API key
   ```

3. **Get Google GenAI API key:**

   - Visit <https://aistudio.google.com/apikey>
   - Create/sign in to Google account and generate API key
   - Add to `.env` as `GOOGLE_API_KEY`

4. **Optional: Enable authentication:**
   - Set `API_KEY` in `.env` to enable X-API-Key header validation
   - Leave unset to disable authentication

### Database Migrations

Database migrations are automatically run on application startup. To manually manage migrations:

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Running

### Development Mode

Using uv:

```bash
uv run uvicorn app.main:app --reload
```

Using Python directly:

```bash
python -m uvicorn app.main:app --reload
```

Using Docker:

```bash
docker build -t text-translation-service .
docker run -p 8000:8000 --env-file .env text-translation-service
```

### Production Mode

Using Python:

```bash
python -m app.main
```

Using Docker:

```bash
docker build -t text-translation-service .
docker run -d -p 8000:8000 --env-file .env text-translation-service
```

Server runs at `http://localhost:8000`

## API Usage

### Base URL

All API endpoints are versioned and prefixed with `/api/v1`

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### Translate SRT File

**Without authentication:**

```bash
curl -X POST http://localhost:8000/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "srt_content": "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n2\n00:00:05,000 --> 00:00:08,000\nHow are you?",
    "target_language": "Spanish"
  }'
```

**With authentication:**

```bash
curl -X POST http://localhost:8000/api/v1/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "srt_content": "...",
    "target_language": "French"
  }'
```

**With localization:**

```bash
curl -X POST http://localhost:8000/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "srt_content": "...",
    "target_language": "Portuguese",
    "country": "Brazil"
  }'
```

**Request parameters:**

- `srt_content` (required): SRT file content as string
- `target_language` (required): Target language (e.g., "Spanish", "French", "Japanese")
- `source_language` (optional): Source language hint
- `country` (optional): Target country/region for localization (e.g., "Brazil", "Spain", "Mexico")
- `model` (optional): Google GenAI model override (default: gemini-2.5-pro)
- `chunk_size` (optional): Number of consecutive entries to translate together (default: 100)

**Response:**

```json
{
  "translated_srt": "1\n00:00:01,000 --> 00:00:04,000\nHola mundo\n\n2\n00:00:05,000 --> 00:00:08,000\n¿Cómo estás?",
  "entry_count": 2
}
```

### Transcribe Audio File

**1. Create transcription job:**

```bash
curl -X POST http://localhost:8000/api/v1/transcriptions \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/audio.mp3",
    "language_code": "en"
  }'
```

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "audio_url": "https://example.com/audio.mp3",
  "language_code": "en",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**2. Check job status:**

```bash
curl http://localhost:8000/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000
```

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "audio_url": "https://example.com/audio.mp3",
  "language_code": "en",
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:32:30Z"
}
```

**3. Download SRT file:**

```bash
curl -L http://localhost:8000/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000/srt \
  -o transcript.srt
```

**Request parameters:**

- `audio_url` (required): URL to audio file (or use S3 presigned URL from upload)
- `language_code` (optional): Language code for transcription (e.g., "en", "es", "fr")

**Job statuses:**

- `queued`: Job created, waiting to start
- `processing`: Transcription in progress
- `completed`: SRT file ready for download
- `failed`: Transcription failed (check error message)

## Interactive Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Testing

The project has 213 tests across 20 test files organized by component (API, services, core, database, storage).

**Quick start:**

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/api/v1/test_transcription.py

# Using test script
bash scripts/test.sh
```

**See [tests/README.md](tests/README.md) for comprehensive testing guide** covering:

- Test organization and structure
- Fixtures and test doubles (FakeAssemblyAIClient, FakeS3Storage)
- Running specific test suites
- Coverage analysis

## Development

### Install dev dependencies

```bash
uv sync --all-extras
```

### Code formatting

```bash
bash scripts/format.sh

# Or manually
black app/ tests/
ruff check app/ tests/ --fix
```

### Linting

```bash
bash scripts/lint.sh

# Or manually
ruff check app/ tests/
```

## Configuration

All configuration is managed through environment variables (see `.env.example`):

### Required

- `GOOGLE_API_KEY`: Google GenAI API key

### Optional - Database

- `DATABASE_PATH`: SQLite database path (default: ./data/transcriptions.db)

### Optional - S3 Storage

- `S3_ENDPOINT_URL`: S3 endpoint URL (default: <https://s3.amazonaws.com>)
- `S3_REGION`: S3 region (default: us-east-1)
- `S3_BUCKET_NAME`: S3 bucket name
- `S3_ACCESS_KEY_ID`: S3 access key
- `S3_SECRET_ACCESS_KEY`: S3 secret key
- `S3_MAX_POOL_CONNECTIONS`: Connection pool size (default: 10)
- `S3_CONNECT_TIMEOUT`: Connection timeout in seconds (default: 60)
- `S3_READ_TIMEOUT`: Read timeout in seconds (default: 60)

### Optional - Transcription

- `ASSEMBLYAI_API_KEY`: AssemblyAI API key for transcription service
- `WEBHOOK_BASE_URL`: Base URL for webhook callbacks
- `WEBHOOK_SECRET_TOKEN`: Secret token for webhook authentication
- `MAX_FILE_SIZE`: Max audio file size (default: 1GB)
- `MAX_CONCURRENT_JOBS`: Max concurrent transcription jobs (default: 10)
- `POLLING_ENABLED`: Enable background polling for stale jobs (default: true)
- `POLLING_INTERVAL`: Polling interval in seconds (default: 300)
- `STALE_JOB_THRESHOLD`: Threshold for stale jobs in seconds (default: 7200)

### Optional - Environment

- `ENVIRONMENT`: Environment name (default: development)

### Optional - Server

- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `ALLOWED_HOSTS`: List of allowed hosts for production (default: ["*"])

### Optional - Authentication

- `API_KEY`: Service authentication key (optional)

### Optional - CORS

- `CORS_ENABLED`: Enable CORS (default: true)
- `CORS_ORIGINS`: Allowed origins (default: ["*"])
- `CORS_ALLOW_CREDENTIALS`: Allow credentials (default: true)
- `CORS_ALLOW_METHODS`: Allowed methods (default: ["*"])
- `CORS_ALLOW_HEADERS`: Allowed headers (default: ["*"])

### Optional - Translation

- `DEFAULT_CHUNK_SIZE`: Translation chunk size (default: 100)
- `MAX_CONCURRENT_REQUESTS`: Max concurrent translation requests (default: 25)

### Optional - Logging

- `LOG_LEVEL`: Logging level (default: INFO)
- `ENABLE_LOG_REDACTION`: Enable automatic redaction of sensitive data in logs (default: true)
  - Redacts: API keys, tokens, S3 URLs, webhook secrets, passwords

## Error Handling

### Translation Errors

- **400 Bad Request**: Invalid SRT format
- **401 Unauthorized**: Missing/invalid API key (if auth enabled)
- **422 Unprocessable Entity**: Invalid request parameters
- **502 Bad Gateway**: Google GenAI API error
- **500 Internal Server Error**: Unexpected error

### Transcription Errors

- **400 Bad Request**: Invalid audio format or SRT not ready yet
- **404 Not Found**: Job ID not found
- **413 Payload Too Large**: Audio file exceeds size limit
- **429 Too Many Requests**: Concurrent job limit reached
- **500 Internal Server Error**: Transcription processing error

## Architecture

### Separation of Concerns

- **`app/api/`**: API routes organized by version (v1, v2, etc.)
- **`app/core/`**: Core configuration, logging, middleware, security
- **`app/db/`**: Database layer with SQLAlchemy models and CRUD operations
- **`app/models/`**: Data models
- **`app/schemas/`**: Pydantic request/response schemas
- **`app/services/`**: Business logic (translation, parsing)
- **`app/storage/`**: Storage layer (S3 wrapper with connection pooling)
- **`alembic/`**: Database migrations
- **`scripts/`**: Utility scripts for deployment and development
- **`tests/`**: Unit and integration tests

### Design Patterns

- **Dependency Injection**: FastAPI's built-in DI for config and services
- **Factory Pattern**: App creation in `main.py`
- **Middleware Pattern**: Authentication, CORS, compression middleware
- **Settings Management**: Pydantic Settings for env var validation
- **API Versioning**: Clean separation of API versions

### Middleware Stack

1. **CORS**: Cross-origin resource sharing (configurable)
2. **GZip**: Response compression for bandwidth optimization
3. **TrustedHost**: Host header validation (production only)
4. **Authentication**: Optional API key validation

## Production Deployment

### Pre-deployment Checklist

1. Set `ENVIRONMENT=production` in `.env`
2. Configure `ALLOWED_HOSTS` with your domain(s)
3. Set strong `API_KEY` if using authentication
4. Configure CORS origins appropriately
5. Run pre-start checks: `bash scripts/prestart.sh`

### Docker Deployment

```bash
# Build image
docker build -t text-translation-service .

# Run container
docker run -d -p 8000:8000 --env-file .env --name translation-service text-translation-service

# View logs
docker logs -f translation-service

# Stop container
docker stop translation-service
docker rm translation-service
```

### Health Checks

The service includes built-in health checks:

- HTTP endpoint: `/api/v1/health`
- Docker healthcheck: Automated container health monitoring

## License

MIT
