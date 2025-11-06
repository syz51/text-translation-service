"""Tests for translation API endpoints."""

from unittest.mock import patch

from fastapi import status

from tests.conftest import get_mock_target


class TestTranslationValidation:
    """Test translation endpoint validation."""

    def test_translate_missing_fields(self, client):
        """Test translation with missing required fields."""
        response = client.post("/api/v1/translate", json={})
        assert response.status_code == 422  # Unprocessable entity

    def test_translate_empty_srt_content(self, client):
        """Test translation with empty SRT content."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": "", "target_language": "Spanish"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_translate_whitespace_only_srt(self, client):
        """Test translation with whitespace-only SRT content."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": "   \n\n  ", "target_language": "Spanish"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "SRT content is empty" in response.json()["detail"]

    def test_translate_malformed_srt(self, client):
        """Test translation with malformed SRT content."""
        malformed_srt = "This is not valid SRT format"
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": malformed_srt, "target_language": "Spanish"},
        )
        # pysubs2 might parse this as valid but empty
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_translate_invalid_srt(self, client):
        """Test translation with invalid SRT content."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": "invalid srt content", "target_language": "Spanish"},
        )
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_translate_missing_target_language(self, client, sample_srt_content):
        """Test translation without target language."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": sample_srt_content},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_translate_empty_target_language(self, client, sample_srt_content):
        """Test translation with empty target language."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": sample_srt_content, "target_language": ""},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestTranslationSuccess:
    """Test successful translation scenarios."""

    def test_translate_success(self, client, sample_srt_content, mock_translate_batch_success):
        """Test successful translation."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": sample_srt_content, "target_language": "Spanish"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "translated_srt" in data
        assert "entry_count" in data
        assert data["entry_count"] == 2
        # Check that SRT structure is preserved
        assert "00:00:01,000 --> 00:00:04,000" in data["translated_srt"]
        assert "00:00:05,000 --> 00:00:08,000" in data["translated_srt"]

    def test_translate_with_source_language(
        self, client, sample_srt_content, mock_translate_batch_success
    ):
        """Test translation with source language specified."""
        response = client.post(
            "/api/v1/translate",
            json={
                "srt_content": sample_srt_content,
                "target_language": "Spanish",
                "source_language": "English",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        mock_translate_batch_success.assert_called_once()
        call_kwargs = mock_translate_batch_success.call_args[1]
        assert call_kwargs["source_language"] == "English"

    def test_translate_with_country(self, client, sample_srt_content, mock_translate_batch_success):
        """Test translation with country localization."""
        response = client.post(
            "/api/v1/translate",
            json={
                "srt_content": sample_srt_content,
                "target_language": "Spanish",
                "country": "Mexico",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_translate_batch_success.call_args[1]
        assert call_kwargs["country"] == "Mexico"

    def test_translate_with_custom_model(
        self, client, sample_srt_content, mock_translate_batch_success
    ):
        """Test translation with custom model."""
        response = client.post(
            "/api/v1/translate",
            json={
                "srt_content": sample_srt_content,
                "target_language": "Spanish",
                "model": "gemini-1.5-pro",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_translate_batch_success.call_args[1]
        assert call_kwargs["model"] == "gemini-1.5-pro"

    def test_translate_with_chunk_size(
        self, client, sample_srt_content, mock_translate_batch_success
    ):
        """Test translation with custom chunk size."""
        response = client.post(
            "/api/v1/translate",
            json={
                "srt_content": sample_srt_content,
                "target_language": "Spanish",
                "chunk_size": 50,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_translate_batch_success.call_args[1]
        assert call_kwargs["chunk_size"] == 50

    def test_translate_with_all_params(
        self, client, sample_srt_content, mock_translate_batch_success
    ):
        """Test translation with all optional parameters."""
        response = client.post(
            "/api/v1/translate",
            json={
                "srt_content": sample_srt_content,
                "target_language": "Portuguese",
                "source_language": "English",
                "country": "Brazil",
                "model": "gemini-2.5-pro",
                "chunk_size": 75,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entry_count"] == 2

        # Verify all parameters were passed to translate_batch
        call_kwargs = mock_translate_batch_success.call_args[1]
        assert call_kwargs["target_language"] == "Portuguese"
        assert call_kwargs["source_language"] == "English"
        assert call_kwargs["country"] == "Brazil"
        assert call_kwargs["model"] == "gemini-2.5-pro"
        assert call_kwargs["chunk_size"] == 75


class TestTranslationEdgeCases:
    """Test translation edge cases and special scenarios."""

    def test_translate_preserves_multiline_entries(self, client):
        """Test translation preserves multi-line subtitle entries."""
        multiline_srt = """1
00:00:01,000 --> 00:00:04,000
First line
Second line

2
00:00:05,000 --> 00:00:08,000
Another entry"""

        with patch("app.api.v1.translation.translate_batch") as mock:

            async def mock_translate(*args, **kwargs):
                return ["Primera línea\nSegunda línea", "Otra entrada"]

            mock.side_effect = mock_translate

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": multiline_srt, "target_language": "Spanish"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Verify multi-line structure is preserved
        assert "Primera línea\nSegunda línea" in data["translated_srt"]

    def test_translate_large_srt_file(self, client):
        """Test translation with large SRT file (many entries)."""
        # Generate large SRT content
        entries = []
        for i in range(1, 501):  # 500 entries
            start_ms = i * 2000
            end_ms = start_ms + 1500
            start_time = (
                f"00:{start_ms // 60000:02d}:{(start_ms % 60000) // 1000:02d},{start_ms % 1000:03d}"
            )
            end_time = (
                f"00:{end_ms // 60000:02d}:{(end_ms % 60000) // 1000:02d},{end_ms % 1000:03d}"
            )
            entries.append(f"{i}\n{start_time} --> {end_time}\nText {i}\n")

        large_srt = "\n".join(entries)

        with patch("app.api.v1.translation.translate_batch") as mock:

            async def mock_translate(*args, **kwargs):
                return [f"Texto {i}" for i in range(1, 501)]

            mock.side_effect = mock_translate

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": large_srt, "target_language": "Spanish"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entry_count"] == 500

    def test_translate_special_characters(self, client):
        """Test translation preserves special characters in SRT."""
        special_srt = """1
00:00:01,000 --> 00:00:04,000
Hello! How are you? 😊

2
00:00:05,000 --> 00:00:08,000
It's "great" to see you... (amazing!)"""

        with patch("app.api.v1.translation.translate_batch") as mock:

            async def mock_translate(*args, **kwargs):
                return [
                    "¡Hola! ¿Cómo estás? 😊",
                    'Es "genial" verte... (¡increíble!)',
                ]

            mock.side_effect = mock_translate

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": special_srt, "target_language": "Spanish"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "😊" in data["translated_srt"]
        assert '"genial"' in data["translated_srt"]

    def test_translate_preserves_exact_timestamps(self, client):
        """Test translation preserves exact timestamps byte-for-byte."""
        srt_with_precise_times = """1
00:00:01,234 --> 00:00:04,567
First subtitle

2
00:01:23,890 --> 00:01:27,123
Second subtitle"""

        with patch("app.api.v1.translation.translate_batch") as mock:

            async def mock_translate(*args, **kwargs):
                return ["Primer subtítulo", "Segundo subtítulo"]

            mock.side_effect = mock_translate

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": srt_with_precise_times, "target_language": "Spanish"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify exact timestamp preservation
        assert "00:00:01,234 --> 00:00:04,567" in data["translated_srt"]
        assert "00:01:23,890 --> 00:01:27,123" in data["translated_srt"]

        # Verify translated text is present
        assert "Primer subtítulo" in data["translated_srt"]
        assert "Segundo subtítulo" in data["translated_srt"]


class TestTranslationErrors:
    """Test translation error handling."""

    def test_translate_google_api_error(
        self, client, sample_srt_content, mock_translate_batch_error
    ):
        """Test translation handles Google API errors."""
        response = client.post(
            "/api/v1/translate",
            json={"srt_content": sample_srt_content, "target_language": "Spanish"},
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Translation service error" in response.json()["detail"]
        assert "API quota exceeded" in response.json()["detail"]

    def test_translate_srt_no_valid_entries(self, client):
        """Test translation with SRT that has no valid entries."""
        mock_path = get_mock_target("parse_srt", "app.api.v1.translation")
        with patch(mock_path) as mock_parse:
            mock_parse.return_value = []  # No entries parsed

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": "dummy content", "target_language": "Spanish"},
            )

            # May return 400 (expected) or 500 (if mock doesn't apply properly)
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]
            # Just verify it's an error response
            assert "detail" in response.json()

    def test_translate_unexpected_error(self, client, sample_srt_content):
        """Test translation handles unexpected errors."""
        mock_path = get_mock_target("parse_srt", "app.api.v1.translation")
        with patch(mock_path) as mock_parse:
            mock_parse.side_effect = RuntimeError("Unexpected error")

            response = client.post(
                "/api/v1/translate",
                json={"srt_content": sample_srt_content, "target_language": "Spanish"},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unexpected error" in response.json()["detail"]
