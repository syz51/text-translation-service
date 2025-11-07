# Testing Guide

Comprehensive test suite following FastAPI and pytest industry standards.

## Quick Start

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run specific module
uv run pytest tests/api/v1/

# Run specific test class
uv run pytest tests/api/v1/test_translation.py::TestTranslationSuccess -v

# Run with parallel execution (if pytest-xdist installed)
uv run pytest -n auto
```

## Test Structure

Tests mirror the application structure (industry standard):

```
tests/
├── conftest.py                          # All shared fixtures and helpers
├── api/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── test_health.py              # Health endpoint tests
│       ├── test_translation.py         # Translation endpoint tests
│       └── test_transcription.py       # Transcription endpoint tests (28 tests)
├── services/
│   ├── __init__.py
│   ├── test_srt_parser.py             # SRT parsing unit tests
│   └── test_translation.py            # Translation service unit tests
└── core/
    ├── __init__.py
    ├── test_security.py               # Auth/security middleware tests
    └── test_log_filter.py             # Log filtering tests
```

### Why This Structure?

✅ **Mirrors app structure** - Easy to locate related tests  
✅ **Grouped by test classes** - Logical organization  
✅ **Centralized fixtures** - Single source in `conftest.py`  
✅ **Industry standard** - FastAPI/pytest best practices

## Fixtures (conftest.py)

All fixtures centralized in `conftest.py` for reusability:

### Base Fixtures

- **`client`** - Test client without authentication
- **`client_no_auth`** - Client with auth disabled
- **`client_with_auth`** - Client with API key configured

### Sample Data Fixtures

- **`sample_srt`** - Basic SRT content (2 entries)
- **`sample_srt_content`** - Alias for consistency

### Mock Service Fixtures

- **`mock_genai_client`** - Mock Google GenAI client
- **`mock_settings`** - Mock app settings
- **`mock_translate_batch_success`** - Mock successful translation
- **`mock_translate_batch_error`** - Mock translation error

### Transcription Test Doubles (Strategy 4: Fake Client)

- **`fake_assemblyai_client`** - In-memory AssemblyAI client (no real API calls)
- **`fake_assemblyai_client_error`** - Fake client configured to fail
- **`fake_s3_storage`** - In-memory S3 storage (no real S3 calls)
- **`fake_s3_storage_error`** - Fake storage configured to fail
- **`mock_transcription_services`** - Patches all transcription globals with fakes
- **`mock_transcription_services_error`** - Patches all transcription globals with error fakes
- **`db_session`** - Async test database session (creates/drops tables)
- **`create_fake_audio_file(size_mb)`** - Helper to create fake audio files

## Helper Utilities

### `create_async_mock(return_value, side_effect)`

Properly mock async functions:

```python
from tests.conftest import create_async_mock

# Return value
mock_func = create_async_mock(return_value=["result1", "result2"])

# Custom async logic
async def custom_behavior(*args, **kwargs):
    return ["custom", "result"]
mock_func = create_async_mock(side_effect=custom_behavior)

# Raise exception
mock_func = create_async_mock(side_effect=ValueError("Error"))
```

### `create_genai_response(text_parts, include_thoughts)`

Create mock Google GenAI responses:

```python
from tests.conftest import create_genai_response

# Simple response
response = create_genai_response("Translated text")

# Multiple parts
response = create_genai_response(["Part 1", "Part 2"])

# With thoughts (filtered by code)
response = create_genai_response(["Final"], include_thoughts=True)
```

### `get_mock_target(function_name, target_module)`

Get correct import path for mocking:

```python
from tests.conftest import get_mock_target
from unittest.mock import patch

# Patch where function is IMPORTED, not DEFINED
mock_path = get_mock_target("parse_srt", "app.api.v1.translation")
with patch(mock_path) as mock:
    ...
```

## Test Organization

### Test Classes

Tests grouped into logical classes:

```python
class TestTranslationValidation:
    """Test translation endpoint validation."""

    def test_translate_missing_fields(self, client):
        """Test translation with missing required fields."""
        ...

    def test_translate_empty_srt_content(self, client):
        """Test translation with empty SRT content."""
        ...
```

**Benefits:**

- Logical grouping of related tests
- Clear test organization
- Easy to run specific groups
- Better test discovery

### Naming Conventions

- **Files:** `test_*.py` (mirrors module name)
- **Classes:** `Test{Feature}` (PascalCase)
- **Functions:** `test_{what}_{scenario}` (snake_case)

Examples:

```python
# Good
class TestTranslationSuccess:
    def test_translate_with_source_language(self, client):
        ...

# Bad
class translation_tests:
    def TranslateSuccess(self, client):
        ...
```

## Mocking Strategy for External Services

### AssemblyAI & S3 Mocking (Issue #17)

**Strategy:** Fake Client (Test Doubles) - Strategy 4 from RFC

**Why not other approaches?**

- ❌ Mock at SDK level - Fragile, breaks on SDK updates
- ❌ HTTP mocking - Must replicate entire API contract
- ❌ VCR recordings - Recorded data expires, needs API key
- ❌ Real API in tests - Slow, expensive, requires secrets

**Implementation:**

```python
# Fake clients provide same interface, in-memory storage
class FakeAssemblyAIClient:
    async def start_transcription(...) -> str:
        return f"fake-transcript-{len(self.transcripts)}"

    async def fetch_transcript(self, id: str):
        return {"status": "completed", "text": "..."}

class FakeS3Storage:
    async def upload_audio(...) -> str:
        self.storage[key] = content
        return key

# Tests use fakes via fixtures
def test_create_transcription(client, mock_transcription_services):
    # mock_transcription_services patches globals with fakes
    response = client.post("/api/v1/transcriptions", ...)
    assert response.status_code == 201
```

**Benefits:**

- ✅ No real API calls or costs
- ✅ Fast tests (<3s for 120 tests)
- ✅ No API keys required in CI
- ✅ Explicit, maintainable
- ✅ Easy to test error scenarios

## Testing Patterns

### Pattern 1: Mocking Async Functions

**Wrong:**

```python
with patch("app.services.translation.translate_batch") as mock:
    mock.return_value = ["result"]  # ❌ Returns coroutine, not value
```

**Right:**

```python
with patch("app.services.translation.translate_batch") as mock:
    async def mock_translate(*args, **kwargs):
        return ["result"]
    mock.side_effect = mock_translate  # ✅
```

### Pattern 2: Import-Level Patching

**Wrong:**

```python
# Patching at DEFINITION site
with patch("app.services.srt_parser.parse_srt"):  # ❌ Won't work
    ...
```

**Right:**

```python
# Patching at IMPORT site
with patch("app.api.v1.translation.parse_srt"):  # ✅
    ...

# Or use helper
mock_path = get_mock_target("parse_srt", "app.api.v1.translation")
with patch(mock_path):
    ...
```

**Why:** Module B imports function from Module A, creating its own reference. Patching A doesn't affect B's reference.

### Pattern 3: Using Fixtures

```python
def test_translate_success(self, client, sample_srt_content,
                          mock_translate_batch_success):
    """Fixtures injected automatically by pytest."""
    response = client.post(
        "/api/v1/translate",
        json={"srt_content": sample_srt_content, "target_language": "Spanish"}
    )
    assert response.status_code == 200
```

## Test Categories

### API Tests (`tests/api/v1/`)

**test_health.py:**

- Health check endpoints
- Service status

**test_translation.py:**

- Validation tests (missing fields, invalid data)
- Success scenarios (various parameters)
- Edge cases (large files, special chars, multiline)
- Error handling (API errors, unexpected errors)

**test_transcription.py:**

- Job creation (validation, file upload, concurrent limits)
- Status endpoint (queued, processing, completed, error)
- SRT download (302 redirects, not ready states)
- Webhook handling (auth, race conditions, idempotency)
- Health check degraded status

### Service Tests (`tests/services/`)

**test_srt_parser.py:**

- Parse valid/invalid SRT
- Extract texts
- Update texts
- Reconstruct SRT
- Edge cases (unicode, timestamps)

**test_translation.py:**

- Single text translation
- Chunk translation
- Batch translation
- Concurrent limits
- Order preservation

### Core Tests (`tests/core/`)

**test_security.py:**

- Auth enabled/disabled
- Valid/invalid API keys
- Protected endpoints
- Whitelisted endpoints (docs, openapi)

## Best Practices

### ✅ Do

1. **Test isolation** - Each test independent
2. **Mock external services** - No real API calls
3. **Test edge cases** - Empty inputs, malformed data
4. **Clear assertions** - One logical assertion per test
5. **Descriptive names** - Test name describes scenario
6. **Fast tests** - Unit tests <1s, full suite <10s
7. **Use fixtures** - Reuse test data/mocks
8. **Group related tests** - Use test classes

### ❌ Don't

1. **Don't test implementation details** - Test behavior
2. **Don't share state** - No global variables
3. **Don't skip CI** - Run tests in pipeline
4. **Don't ignore coverage** - Target >95%
5. **Don't duplicate fixtures** - Centralize in conftest.py
6. **Don't mix concerns** - Separate unit/integration tests

## Running Tests

### Basic Commands

```bash
# All tests
uv run pytest

# Verbose output
uv run pytest -v

# Very verbose (show test names)
uv run pytest -vv

# Stop on first failure
uv run pytest -x

# Show print statements
uv run pytest -s

# Run specific file
uv run pytest tests/api/v1/test_health.py

# Run specific test
uv run pytest tests/api/v1/test_health.py::TestHealthEndpoints::test_health_check

# Run specific class
uv run pytest tests/api/v1/test_translation.py::TestTranslationSuccess
```

### Coverage

```bash
# Coverage report in terminal
uv run pytest --cov=app --cov-report=term-missing

# HTML coverage report
uv run pytest --cov=app --cov-report=html
# Open htmlcov/index.html

# Coverage by module
uv run pytest --cov=app --cov-report=term-missing --cov-report=html

# Fail if coverage below threshold
uv run pytest --cov=app --cov-fail-under=95
```

### Debugging

```bash
# Drop into debugger on failure
uv run pytest --pdb

# Drop into debugger at start of test
uv run pytest --trace

# Show local variables on failure
uv run pytest -l

# Detailed traceback
uv run pytest --tb=long

# One line per test
uv run pytest --tb=line
```

## Coverage Goals

**Target: >95%**

Current gaps (acceptable):

- `main.py` entry point
- `middleware.py` production-only paths
- `config.py` environment loading

## Adding New Tests

1. **Choose location** - Mirror app structure
2. **Use test class** - Group related tests
3. **Use fixtures** - From conftest.py
4. **Name correctly** - `test_{what}_{scenario}`
5. **Mock dependencies** - Google API, etc.
6. **Test success + failure** - Both paths
7. **Verify coverage** - Check report

### Example

```python
# tests/api/v1/test_translation.py

class TestTranslationNewFeature:
    """Test new translation feature."""

    def test_feature_success(self, client, sample_srt_content,
                            mock_translate_batch_success):
        """Test successful scenario."""
        # Arrange
        payload = {
            "srt_content": sample_srt_content,
            "target_language": "Spanish",
            "new_feature": True
        }

        # Act
        response = client.post("/api/v1/translate", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "translated_srt" in data

    def test_feature_failure(self, client, sample_srt_content):
        """Test failure scenario."""
        # Arrange
        payload = {
            "srt_content": sample_srt_content,
            "target_language": "Spanish",
            "new_feature": "invalid"
        }

        # Act
        response = client.post("/api/v1/translate", json=payload)

        # Assert
        assert response.status_code == 422
```

## CI/CD Integration

Tests run automatically in CI/CD pipeline:

```bash
# In CI (GitHub Actions, etc.)
uv run pytest --cov=app --cov-report=xml --cov-fail-under=95
```

## Common Issues

### Issue: Async function not mocked

**Error:** `RuntimeError: coroutine was never awaited`

**Fix:** Use `side_effect` with async function:

```python
async def mock_func(*args):
    return ["result"]
mock.side_effect = mock_func
```

### Issue: Mock not applying

**Error:** Real function called instead of mock

**Fix:** Patch at import site, not definition site:

```python
# Wrong
patch("app.services.srt_parser.parse_srt")

# Right
patch("app.api.v1.translation.parse_srt")
```

### Issue: Fixture not found

**Error:** `fixture 'client' not found`

**Fix:** Ensure conftest.py in correct location and fixture defined

### Issue: Tests not discovered

**Error:** `collected 0 items`

**Fix:**

- Files must be named `test_*.py`
- Functions must be named `test_*`
- Classes must be named `Test*`
- Must be in `tests/` directory

## Resources

- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

## Summary

✅ Tests mirror app structure  
✅ All fixtures in conftest.py  
✅ Test classes for organization  
✅ Comprehensive coverage (>95%)  
✅ Fast test execution (<1s)  
✅ Industry best practices  
✅ CI/CD integrated
