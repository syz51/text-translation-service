"""Tests for health check endpoints."""

from fastapi import status


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/")
        assert response.status_code == status.HTTP_200_OK
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

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ["running", "degraded"]
        assert "components" in data
        assert "assemblyai" in data["components"]
        assert "s3_storage" in data["components"]
