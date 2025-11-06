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
        assert data["status"] == "running"
        assert "version" in data
        assert "authentication" in data

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "running"
