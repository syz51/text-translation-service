# Transcription API Tests

## Coverage: 96% ✅

The transcription API has comprehensive test coverage with a clear separation between unit tests (direct endpoint calls) and integration tests (HTTP layer).

## Test Structure

### `test_transcription_direct.py` (27 tests)

**Purpose:** Test endpoint business logic directly for proper coverage tracking

**Tests:**

- ✅ All success paths (create, status, download, webhook)
- ✅ Error handling (file read errors, DB errors, S3 failures, AssemblyAI errors)
- ✅ Validation (format, size, concurrent limits)
- ✅ Edge cases (missing configs, webhook auth, background processing)

**Why direct calls:**

- TestClient doesn't work well with coverage.py
- Direct function calls ensure coverage.py tracks execution properly
- Faster execution (no HTTP overhead)

### `test_transcription_integration.py` (11 tests)

**Purpose:** Validate HTTP layer and integration concerns

**Tests:**

- ✅ HTTP request/response cycle (status codes, headers, JSON)
- ✅ File upload (multipart/form-data handling)
- ✅ Race conditions (webhook timing)
- ✅ Concurrent job limits (integration-level)
- ✅ Health check endpoint

**Why TestClient:**

- Validates full HTTP stack including middleware
- Tests multipart file upload handling
- Catches HTTP-specific issues (redirects, headers)

## Running Tests

```bash
# Run all transcription API tests (recommended)
ASSEMBLYAI_API_KEY= uv run pytest tests/api/v1/test_transcription_*.py -v

# Run unit tests only (fastest, best for TDD)
ASSEMBLYAI_API_KEY= uv run pytest tests/api/v1/test_transcription_direct.py -v

# Run integration tests only (HTTP layer)
ASSEMBLYAI_API_KEY= uv run pytest tests/api/v1/test_transcription_integration.py -v

# Check coverage
ASSEMBLYAI_API_KEY= uv run coverage run --source=app -m pytest tests/api/v1/test_transcription_direct.py
uv run coverage report --include="app/api/v1/transcription.py"
```

## Coverage Details

**Total: 96% (142 statements, 5 missing)**

Uncovered lines (4%):

- Line 157: S3 upload exception re-raise path
- Lines 166-167: Nested exception handling in S3 error recovery
- Lines 433-434: Nested exception handling in background processing

These are defensive error handling paths that are difficult to trigger in tests but provide important safety.

## Key Improvements

### Problem Identified

1. **TestClient Coverage Issue:** FastAPI's TestClient runs requests in a way that coverage.py can't track properly. Tests passed but coverage showed 26%.

2. **Mock Signature Mismatches:** Fake service implementations had incorrect method signatures that didn't match real services.

### Solution

1. **Fixed Mock Implementations** (`tests/conftest.py`):

   - Corrected all method signatures to exactly match real services
   - Fixed parameter order, types, and async behavior
   - Example: `FakeS3Storage.upload_audio(job_id, file)` now matches real signature

2. **Direct Endpoint Tests:**

   - Call endpoint functions directly instead of via TestClient
   - Coverage.py can now properly track execution
   - Comprehensive error path testing

3. **Focused Integration Tests:**
   - Kept valuable HTTP-layer tests
   - Removed duplication with direct tests
   - Focus on timing, race conditions, HTTP-specific behavior

## Test Fixtures

Defined in `tests/conftest.py`:

- **`db_session`** - Test database session with automatic cleanup
- **`client`** - TestClient without authentication
- **`mock_transcription_services`** - Patches global S3 and AssemblyAI clients
- **`FakeS3Storage`** - In-memory S3 implementation
- **`FakeAssemblyAIClient`** - In-memory AssemblyAI implementation
- **`create_fake_audio_file(size_mb)`** - Generate fake audio data

## Best Practices

### When Writing New Tests

1. **Start with direct tests** for business logic and coverage
2. **Add integration tests** for HTTP-specific behavior
3. **Ensure mocks match real signatures exactly**
4. **Test both success and error paths**
5. **Use direct calls for coverage, TestClient for integration**

### Example: Testing a New Endpoint

```python
# test_new_endpoint_direct.py - For coverage
@pytest.mark.asyncio
async def test_new_endpoint_success(db_session, mock_services):
    result = await new_endpoint(param=value, session=db_session)
    assert result.status == "success"

# test_new_endpoint_integration.py - For HTTP layer
def test_new_endpoint_http(client, mock_services):
    response = client.post("/api/v1/new-endpoint", json={"param": "value"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
```

## Resources

- **Conftest:** `tests/conftest.py` - All fixtures and mocks
- **Service Tests:** `tests/services/` - Lower-level service unit tests
- **Storage Tests:** `tests/storage/` - S3 client tests
