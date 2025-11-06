"""Tests for health check endpoints."""

from fastapi import status


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/")
        # Accept 200 (all healthy) or 503 (degraded, e.g., S3 not initialized in tests)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()
        assert data["service"] == "Text Translation Service"
        assert data["status"] in ["running", "degraded"]
        assert "version" in data
        assert "authentication" in data
        assert "components" in data
        assert "assemblyai" in data["components"]
        assert "s3_storage" in data["components"]
        assert data["components"]["assemblyai"]["status"] in ["healthy", "unhealthy"]
        assert data["components"]["s3_storage"]["status"] in ["healthy", "unhealthy"]
        # Verify endpoints field is present
        assert "endpoints" in data
        assert "translation" in data["endpoints"]
        assert "transcription" in data["endpoints"]
        assert "health" in data["endpoints"]

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/api/v1/health")
        # Accept 200 (all healthy) or 503 (degraded, e.g., S3 not initialized in tests)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()
        assert data["status"] in ["running", "degraded"]
        assert "components" in data
        assert "assemblyai" in data["components"]
        assert "s3_storage" in data["components"]
        # Verify endpoints field is present
        assert "endpoints" in data
        assert isinstance(data["endpoints"], dict)
