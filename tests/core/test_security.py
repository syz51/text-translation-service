"""Tests for security and authentication middleware."""

from fastapi import status


class TestAuthenticationMiddleware:
    """Tests for API key authentication."""

    def test_health_endpoint_with_auth_configured(self, client_with_auth):
        """Test health endpoint requires auth when API key is configured."""
        # Versioned endpoints are NOT in the whitelist, so they need auth
        response = client_with_auth.get("/api/v1/health")
        # Should be 401 because /api/v1/health is not in the whitelist
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_root_health_with_auth_configured(self, client_with_auth):
        """Test root health endpoint requires auth when API key is configured."""
        # Versioned endpoints are NOT in the whitelist, so they need auth
        response = client_with_auth.get("/api/v1/")
        # Should be 401 because /api/v1/ is not in the whitelist
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_docs_no_auth_required(self, client_with_auth):
        """Test docs endpoints accessible without auth."""
        response = client_with_auth.get("/docs")
        assert response.status_code == status.HTTP_200_OK

    def test_openapi_no_auth_required(self, client_with_auth):
        """Test OpenAPI JSON accessible without auth."""
        response = client_with_auth.get("/openapi.json")
        assert response.status_code == status.HTTP_200_OK

    def test_protected_endpoint_with_no_auth_configured(self, client_no_auth):
        """Test protected endpoint accessible when auth not configured."""
        # Should pass through when no API key is set
        response = client_no_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
        )
        # Will fail on validation or other reasons, but NOT 401
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    def test_protected_endpoint_missing_api_key_header(self, client_with_auth):
        """Test protected endpoint rejects request without API key header."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing X-API-Key header" in response.json()["detail"]

    def test_protected_endpoint_invalid_api_key(self, client_with_auth):
        """Test protected endpoint rejects invalid API key."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
            headers={"X-API-Key": "wrong_key"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in response.json()["detail"]

    def test_protected_endpoint_valid_api_key(self, client_with_auth):
        """Test protected endpoint accepts valid API key."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
            headers={"X-API-Key": "test_secret_key_12345"},
        )
        # Will fail on SRT parsing, but NOT on auth (not 401)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    def test_case_sensitive_api_key(self, client_with_auth):
        """Test API key comparison is case-sensitive."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
            headers={"X-API-Key": "TEST_SECRET_KEY_12345"},  # Wrong case
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_api_key_header(self, client_with_auth):
        """Test empty API key header is rejected."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
            headers={"X-API-Key": ""},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_whitespace_api_key(self, client_with_auth):
        """Test API key with whitespace is rejected."""
        response = client_with_auth.post(
            "/api/v1/translate",
            json={"srt_content": "test", "target_language": "Spanish"},
            headers={"X-API-Key": " test_secret_key_12345 "},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
