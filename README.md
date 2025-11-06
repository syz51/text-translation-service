# Text Translation Service

Production-grade FastAPI service for translating SRT subtitle files using Google GenAI's Gemini 2.5 Pro model, with transcription API capabilities (in development).

## Features

### Translation Service

- **SRT Format Support**: Preserves timestamps and structure
- **Enhanced Translation**: Multi-step reasoning with extended thinking for subtitle-optimized translations
- **Localization Support**: Optional country/region parameter for cultural adaptation
- **Contextual Chunking**: Groups consecutive entries for better translation context and quality
- **Concurrent Processing**: Handles multiple chunks simultaneously for speed
- **Google GenAI Integration**: Uses Gemini 2.5 Pro with extended thinking

### Infrastructure

- **Database Layer**: SQLAlchemy 2.0 with async support and Alembic migrations
- **S3 Storage**: Production-grade S3 wrapper with connection pooling for audio/SRT files
- **API Key Authentication**: Optional authentication layer
- **Auto Documentation**: Interactive API docs at `/docs`
- **Production Ready**: Proper project structure, logging, config management, CORS, middleware, and tests
- **API Versioning**: Clean v1 API structure with room for future versions

## Project Structure

```
text-translation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/                 # API v1 routes
│   │       ├── __init__.py
│   │       ├── health.py       # Health check endpoints
│   │       └── translation.py  # Translation endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Settings management
│   │   ├── logging.py          # Logging setup
│   │   ├── middleware.py       # Middleware configuration
│   │   └── security.py         # Auth middleware
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py             # SQLAlchemy setup
│   │   ├── crud.py             # Database operations
│   │   └── models.py           # Database models
│   ├── models/
│   │   ├── __init__.py
│   │   └── srt.py              # SRT data models
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── translation.py      # Request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── srt_parser.py       # SRT parsing logic
│   │   └── translation.py      # Translation service
│   └── storage/
│       ├── __init__.py
│       └── s3.py               # S3 storage wrapper
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
│   ├── conftest.py             # Test fixtures
│   ├── test_api.py             # API tests
│   └── test_srt_parser.py      # Parser tests
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml          # Production compose
├── docker-compose.dev.yml      # Development compose
├── Dockerfile
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker & Docker Compose (optional)

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

### Development Mode (Local)

Using uv:

```bash
uv run uvicorn app.main:app --reload
```

Using Python directly:

```bash
python -m uvicorn app.main:app --reload
```

### Development Mode (Docker)

```bash
docker compose -f docker-compose.dev.yml up --build
```

### Production Mode (Docker)

```bash
docker compose up -d
```

### Production Mode (Local)

```bash
python -m app.main
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

## Interactive Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Testing

Run tests:

```bash
# Using uv
uv run pytest

# Using pytest directly
pytest

# With coverage (using script)
bash scripts/test.sh

# With coverage (manual)
pytest --cov=app --cov-report=html
```

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

- `S3_ENDPOINT_URL`: S3 endpoint URL (default: https://s3.amazonaws.com)
- `S3_REGION`: S3 region (default: us-east-1)
- `S3_BUCKET_NAME`: S3 bucket name
- `S3_ACCESS_KEY_ID`: S3 access key
- `S3_SECRET_ACCESS_KEY`: S3 secret key
- `S3_MAX_POOL_CONNECTIONS`: Connection pool size (default: 10)
- `S3_CONNECT_TIMEOUT`: Connection timeout in seconds (default: 60)
- `S3_READ_TIMEOUT`: Read timeout in seconds (default: 60)

### Optional - Transcription (Future)

- `ASSEMBLYAI_API_KEY`: AssemblyAI API key for transcription service
- `WEBHOOK_BASE_URL`: Base URL for webhook callbacks
- `WEBHOOK_SECRET_TOKEN`: Secret token for webhook authentication
- `MAX_FILE_SIZE`: Max audio file size (default: 1GB)
- `MAX_CONCURRENT_JOBS`: Max concurrent transcription jobs (default: 10)

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

## Error Handling

- **400 Bad Request**: Invalid SRT format
- **401 Unauthorized**: Missing/invalid API key (if auth enabled)
- **422 Unprocessable Entity**: Invalid request parameters
- **502 Bad Gateway**: Google GenAI API error
- **500 Internal Server Error**: Unexpected error

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
# Build and run
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Health Checks

The service includes built-in health checks:

- HTTP endpoint: `/api/v1/health`
- Docker healthcheck: Automated container health monitoring

## License

MIT
