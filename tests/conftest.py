"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app

# ============================================================================
# Base Fixtures
# ============================================================================


@pytest.fixture
async def db_session():
    """Create test database session."""
    from app.db.base import Base, SessionLocal, engine

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with SessionLocal() as session:
        yield session

    # Cleanup tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def init_test_db():
    """Initialize test database tables."""
    from app.db.base import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_service_connectivity(fake_assemblyai_client, fake_s3_storage, monkeypatch):
    """Mock all external service connectivity tests.

    Patches global client instances to avoid requiring real API keys.
    """
    # Patch global instances to use fakes (avoids API key requirement)
    monkeypatch.setattr("app.api.v1.health.assemblyai_client", fake_assemblyai_client)
    monkeypatch.setattr("app.api.v1.health.s3_storage", fake_s3_storage)

    # Also patch the connectivity methods for explicit control
    assemblyai_path = "app.services.assemblyai_client.assemblyai_client.test_connectivity"
    s3_path = "app.storage.s3.s3_storage.test_connectivity"
    with (
        patch(assemblyai_path, new_callable=AsyncMock) as mock_assemblyai,
        patch(s3_path, new_callable=AsyncMock) as mock_s3,
    ):
        # Default to healthy services
        mock_assemblyai.return_value = True
        mock_s3.return_value = True
        yield {
            "assemblyai": mock_assemblyai,
            "s3": mock_s3,
        }


@pytest.fixture
def client(mock_service_connectivity, init_test_db):
    """Create test client without authentication."""
    app = create_app()
    return TestClient(app)


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_srt():
    """Sample SRT content for testing."""
    return """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?"""


@pytest.fixture
def sample_srt_content():
    """Sample valid SRT content (alias for consistency)."""
    return """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?"""


# ============================================================================
# Mock Service Fixtures
# ============================================================================


@pytest.fixture
def mock_genai_client():
    """Mock Google GenAI client."""
    with patch("app.services.translation.genai.Client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_settings():
    """Mock settings with API key and defaults."""
    with patch("app.services.translation.settings") as mock_settings:
        mock_settings.google_api_key = "test_api_key"
        mock_settings.default_model = "gemini-2.5-pro"
        mock_settings.default_chunk_size = 100
        mock_settings.max_concurrent_requests = 25
        yield mock_settings


@pytest.fixture
def mock_translate_batch_success():
    """Mock successful translate_batch for API integration tests."""
    with patch("app.api.v1.translation.translate_batch") as mock:

        async def mock_translate(*args, **kwargs):
            return ["Hola mundo", "¿Cómo estás?"]

        mock.side_effect = mock_translate
        yield mock


@pytest.fixture
def mock_translate_batch_error():
    """Mock translate_batch with GoogleGenAIError for API tests."""
    with patch("app.api.v1.translation.translate_batch") as mock:
        from app.services.translation import GoogleGenAIError

        async def mock_translate(*args, **kwargs):
            raise GoogleGenAIError("API quota exceeded")

        mock.side_effect = mock_translate
        yield mock


# ============================================================================
# Authentication/Security Fixtures
# ============================================================================


@pytest.fixture
def client_no_auth(mock_service_connectivity):
    """Client with no API key configured."""
    with patch("app.core.security.settings") as mock_settings:
        mock_settings.api_key = None
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_with_auth(mock_service_connectivity, init_test_db):
    """Client with API key configured (no default headers)."""
    with patch("app.core.security.settings") as mock_settings:
        mock_settings.api_key = "test_secret_key_12345"
        app = create_app()
        yield TestClient(app)


def create_async_mock(return_value=None, side_effect=None):
    """Create an AsyncMock that properly handles async function calls.

    This helper ensures async functions are mocked correctly without
    having to use AsyncMock().return_value pattern or side_effect workarounds.

    Args:
        return_value: Value to return from the async function
        side_effect: Function or exception to use as side effect

    Returns:
        Properly configured AsyncMock

    Example:
        # Mock an async function to return a value
        mock_func = create_async_mock(return_value=["translated1", "translated2"])

        # Mock an async function with custom logic
        async def custom_behavior(*args, **kwargs):
            return ["custom", "result"]
        mock_func = create_async_mock(side_effect=custom_behavior)

        # Mock an async function to raise an exception
        mock_func = create_async_mock(side_effect=ValueError("Error"))
    """
    mock = AsyncMock()
    if side_effect is not None:
        mock.side_effect = side_effect
    elif return_value is not None:
        mock.return_value = return_value
    return mock


def create_genai_response(text_parts, include_thoughts=False):
    """Create a mock Google GenAI API response.

    Helper to construct realistic response objects from the Google GenAI API
    without needing to hit the actual API.

    Args:
        text_parts: List of text strings or single text string to return
        include_thoughts: Whether to include thought parts (should be filtered)

    Returns:
        Mock response object matching Google GenAI structure

    Example:
        # Simple response with one text part
        response = create_genai_response("Translated text")

        # Response with multiple parts (thoughts + text)
        response = create_genai_response(["Final text"], include_thoughts=True)
    """
    if isinstance(text_parts, str):
        text_parts = [text_parts]

    parts = []

    if include_thoughts:
        thought_part = MagicMock()
        thought_part.text = "Internal reasoning..."
        thought_part.thought = True
        parts.append(thought_part)

    for text in text_parts:
        text_part = MagicMock()
        text_part.text = text
        text_part.thought = False
        parts.append(text_part)

    response = MagicMock()
    response.candidates = [MagicMock(content=MagicMock(parts=parts))]
    return response


def get_mock_target(function_name, target_module):
    """Get the correct import path for mocking a function.

    When using patch/Mock, you must patch where a function is IMPORTED,
    not where it's DEFINED. This helper constructs the correct path.

    Args:
        function_name: Name of the function to mock (e.g., "parse_srt")
        target_module: Module where the function is imported and used
                      (e.g., "app.api.v1.translation")

    Returns:
        Full patch path string

    Example:
        # Wrong: Patching where function is defined
        with patch("app.services.srt_parser.parse_srt"):  # Won't work!
            ...

        # Right: Patching where function is imported
        path = get_mock_target("parse_srt", "app.api.v1.translation")
        with patch(path):  # app.api.v1.translation.parse_srt
            ...

    Why: If module A imports function from module B, and module C imports
    from A, then C sees A's reference. Patching B won't affect A's reference.
    """
    return f"{target_module}.{function_name}"


# ============================================================================
# Test Doubles for Transcription Services
# ============================================================================


class FakeAssemblyAIClient:
    """Test double for AssemblyAI client.

    Follows Strategy 4 (Fake Client) from issue #17 - provides in-memory
    implementation of AssemblyAI client interface without real API calls.
    """

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.transcripts = {}

    async def start_transcription(
        self,
        presigned_url: str,
        webhook_url: str,
        language_detection: bool = False,
        speaker_labels: bool = False,
    ) -> str:
        """Start fake transcription and return transcript ID."""
        if self.should_fail:
            raise Exception("AssemblyAI API error")
        transcript_id = f"fake-transcript-{len(self.transcripts)}"
        self.transcripts[transcript_id] = {"status": "processing", "text": None}
        return transcript_id

    async def fetch_transcript(self, transcript_id: str):
        """Fetch fake transcript."""
        if transcript_id not in self.transcripts:
            raise ValueError(f"Transcript {transcript_id} not found")
        mock_transcript = MagicMock()
        mock_transcript.text = "This is a fake transcript."
        mock_transcript.status = "completed"
        return mock_transcript

    def convert_to_srt(self, transcript) -> str:
        """Convert fake transcript to SRT format."""
        return "1\n00:00:00,000 --> 00:00:05,000\nThis is a fake transcript.\n"

    async def test_connectivity(self) -> bool:
        """Test connectivity (for health checks)."""
        return not self.should_fail


class FakeS3Storage:
    """Test double for S3 storage.

    Provides in-memory storage implementation without real S3 calls.
    """

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.storage = {}

    async def upload_audio(self, file_content: bytes, job_id: str) -> str:
        """Upload fake audio file to in-memory storage."""
        if self.should_fail:
            raise Exception("S3 upload failed")
        key = f"audio/{job_id}.mp3"
        self.storage[key] = file_content
        return key

    async def upload_srt(self, srt_content: str, job_id: str) -> str:
        """Upload fake SRT file to in-memory storage."""
        if self.should_fail:
            raise Exception("S3 upload failed")
        key = f"srt/{job_id}.srt"
        self.storage[key] = srt_content
        return key

    async def generate_presigned_url(self, key: str, expiry: int = 3600) -> str:
        """Generate fake presigned URL."""
        if key not in self.storage:
            raise ValueError(f"Key {key} not found")
        return f"https://fake-s3.amazonaws.com/{key}?expires={expiry}"

    async def test_connectivity(self) -> bool:
        """Test connectivity (for health checks)."""
        return not self.should_fail


# ============================================================================
# Transcription Service Fixtures
# ============================================================================


@pytest.fixture
def fake_assemblyai_client():
    """Fake AssemblyAI client for testing."""
    return FakeAssemblyAIClient()


@pytest.fixture
def fake_assemblyai_client_error():
    """Fake AssemblyAI client configured to fail."""
    return FakeAssemblyAIClient(should_fail=True)


@pytest.fixture
def fake_s3_storage():
    """Fake S3 storage for testing."""
    return FakeS3Storage()


@pytest.fixture
def fake_s3_storage_error():
    """Fake S3 storage configured to fail."""
    return FakeS3Storage(should_fail=True)


@pytest.fixture
def mock_transcription_services(monkeypatch, fake_assemblyai_client, fake_s3_storage):
    """Mock global instances for transcription tests.

    Patches assemblyai_client and s3_storage global instances used in
    transcription endpoints and service layer.
    """
    monkeypatch.setattr("app.api.v1.transcription.assemblyai_client", fake_assemblyai_client)
    monkeypatch.setattr("app.api.v1.transcription.s3_storage", fake_s3_storage)
    monkeypatch.setattr("app.api.v1.health.assemblyai_client", fake_assemblyai_client)
    monkeypatch.setattr("app.api.v1.health.s3_storage", fake_s3_storage)
    monkeypatch.setattr(
        "app.services.transcription_service.assemblyai_client",
        fake_assemblyai_client,
    )
    monkeypatch.setattr("app.services.transcription_service.s3_storage", fake_s3_storage)
    return {"assemblyai": fake_assemblyai_client, "s3": fake_s3_storage}


@pytest.fixture
def mock_transcription_services_error(
    monkeypatch, fake_assemblyai_client_error, fake_s3_storage_error
):
    """Mock services configured to fail for error testing."""
    monkeypatch.setattr("app.api.v1.transcription.assemblyai_client", fake_assemblyai_client_error)
    monkeypatch.setattr("app.api.v1.transcription.s3_storage", fake_s3_storage_error)
    monkeypatch.setattr("app.api.v1.health.assemblyai_client", fake_assemblyai_client_error)
    monkeypatch.setattr("app.api.v1.health.s3_storage", fake_s3_storage_error)
    monkeypatch.setattr(
        "app.services.transcription_service.assemblyai_client",
        fake_assemblyai_client_error,
    )
    monkeypatch.setattr("app.services.transcription_service.s3_storage", fake_s3_storage_error)
    return {"assemblyai": fake_assemblyai_client_error, "s3": fake_s3_storage_error}


# ============================================================================
# Transcription Test Helper Functions
# ============================================================================


def create_fake_audio_file(size_mb=1):
    """Create fake audio file for testing.

    Args:
        size_mb: Size of fake audio file in megabytes

    Returns:
        BytesIO: Fake audio file object
    """
    from io import BytesIO

    data = b"fake audio data " * (size_mb * 1024 * 64)
    return BytesIO(data)
