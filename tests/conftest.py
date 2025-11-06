"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app

# ============================================================================
# Base Fixtures
# ============================================================================


@pytest.fixture
def mock_service_connectivity():
    """Mock all external service connectivity tests."""
    assemblyai_path = "app.services.assemblyai_client.assemblyai_client.test_connectivity"
    s3_path = "app.storage.s3.s3_storage.test_connectivity"
    with patch(assemblyai_path, new_callable=AsyncMock) as mock_assemblyai, \
         patch(s3_path, new_callable=AsyncMock) as mock_s3:
        # Default to healthy services
        mock_assemblyai.return_value = True
        mock_s3.return_value = True
        yield {
            "assemblyai": mock_assemblyai,
            "s3": mock_s3,
        }


@pytest.fixture
def client(mock_service_connectivity):
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
def client_with_auth(mock_service_connectivity):
    """Client with API key configured."""
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
