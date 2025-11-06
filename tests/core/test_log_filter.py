"""Tests for sensitive data redaction in logs."""

import logging

import pytest

from app.core.log_filter import SensitiveDataFilter


class TestSensitiveDataFilter:
    """Test suite for SensitiveDataFilter."""

    @pytest.fixture
    def log_filter(self):
        """Create a SensitiveDataFilter instance."""
        return SensitiveDataFilter()

    @pytest.fixture
    def log_record(self):
        """Create a basic log record for testing."""
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )

    def test_redact_api_key_with_equals(self, log_filter, log_record):
        """Test redaction of API key with equals sign."""
        log_record.msg = "Starting with api_key=sk_live_abc123def456ghi789"
        log_filter.filter(log_record)
        assert "sk_live_abc123def456ghi789" not in log_record.msg
        assert "***REDACTED***" in log_record.msg

    def test_redact_api_key_with_colon(self, log_filter, log_record):
        """Test redaction of API key with colon."""
        log_record.msg = "Config: apikey: AIzaSyD1234567890abcdefghijk"
        log_filter.filter(log_record)
        assert "AIzaSyD1234567890abcdefghijk" not in log_record.msg
        assert "***REDACTED***" in log_record.msg

    def test_redact_environment_variable(self, log_filter, log_record):
        """Test redaction of environment variables."""
        log_record.msg = "Loading config: GOOGLE_API_KEY=AIzaSyABCDEF123456"
        log_filter.filter(log_record)
        assert "AIzaSyABCDEF123456" not in log_record.msg
        assert "GOOGLE_API_KEY=***REDACTED***" in log_record.msg

    def test_redact_assemblyai_api_key(self, log_filter, log_record):
        """Test redaction of AssemblyAI API key."""
        log_record.msg = "ASSEMBLYAI_API_KEY=abcd1234efgh5678ijkl"
        log_filter.filter(log_record)
        assert "abcd1234efgh5678ijkl" not in log_record.msg
        assert "ASSEMBLYAI_API_KEY=***REDACTED***" in log_record.msg

    def test_redact_webhook_secret(self, log_filter, log_record):
        """Test redaction of webhook secret token."""
        log_record.msg = "WEBHOOK_SECRET_TOKEN=my_secret_webhook_token_12345"
        log_filter.filter(log_record)
        assert "my_secret_webhook_token_12345" not in log_record.msg
        assert "WEBHOOK_SECRET_TOKEN=***REDACTED***" in log_record.msg

    def test_redact_s3_secret_key(self, log_filter, log_record):
        """Test redaction of S3 secret access key."""
        log_record.msg = "S3_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        log_filter.filter(log_record)
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in log_record.msg
        assert "S3_SECRET_ACCESS_KEY=***REDACTED***" in log_record.msg

    def test_redact_authorization_header(self, log_filter, log_record):
        """Test redaction of Authorization header."""
        log_record.msg = "Request headers: Authorization: Bearer abc123xyz789"
        log_filter.filter(log_record)
        assert "abc123xyz789" not in log_record.msg
        assert "Authorization: ***REDACTED***" in log_record.msg

    def test_redact_x_api_key_header(self, log_filter, log_record):
        """Test redaction of X-API-Key header."""
        log_record.msg = "Headers: X-API-Key: sk_test_abc123"
        log_filter.filter(log_record)
        assert "sk_test_abc123" not in log_record.msg
        assert "X-API-Key: ***REDACTED***" in log_record.msg

    def test_redact_bearer_token(self, log_filter, log_record):
        """Test redaction of Bearer token."""
        log_record.msg = "Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        log_filter.filter(log_record)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in log_record.msg
        assert "Bearer ***REDACTED***" in log_record.msg

    def test_redact_presigned_url(self, log_filter, log_record):
        """Test redaction of S3 presigned URL."""
        url = "https://my-bucket.s3.amazonaws.com/audio/file.mp3?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=signature&Expires=1234567890"
        log_record.msg = f"Generated presigned URL: {url}"
        log_filter.filter(log_record)
        # URL base should be preserved, query params redacted
        assert "my-bucket.s3.amazonaws.com/audio/file.mp3" in log_record.msg
        assert "AWSAccessKeyId" not in log_record.msg
        assert "Signature" not in log_record.msg
        assert "***REDACTED***" in log_record.msg

    def test_redact_webhook_url_with_token(self, log_filter, log_record):
        """Test redaction of webhook URL containing secret token."""
        log_record.msg = "Webhook URL: https://api.example.com/webhooks/assemblyai/my_super_secret_token_123456"
        log_filter.filter(log_record)
        assert "my_super_secret_token_123456" not in log_record.msg
        assert "/webhooks/assemblyai/***REDACTED***" in log_record.msg

    def test_redact_generic_secret(self, log_filter, log_record):
        """Test redaction of generic long secret strings."""
        log_record.msg = "Database password: abc123def456ghi789jkl012mno345pqr678"
        log_filter.filter(log_record)
        assert "abc123def456ghi789jkl012mno345pqr678" not in log_record.msg
        assert "***REDACTED***" in log_record.msg

    def test_redact_log_args_tuple(self, log_filter, log_record):
        """Test redaction of log record args (tuple)."""
        log_record.msg = "API call with key: %s"
        log_record.args = ("sk_live_abc123def456ghi789",)
        log_filter.filter(log_record)
        assert "sk_live_abc123def456ghi789" not in log_record.args[0]
        assert "***REDACTED***" in log_record.args[0]

    def test_redact_log_args_dict(self, log_filter, log_record):
        """Test redaction of log record args (dict)."""
        log_record.msg = "Config: %(api_key)s"
        log_record.args = {"api_key": "GOOGLE_API_KEY=AIzaSyABCDEF123456"}
        log_filter.filter(log_record)
        assert "AIzaSyABCDEF123456" not in log_record.args["api_key"]
        assert "***REDACTED***" in log_record.args["api_key"]

    def test_redact_exception_text(self, log_filter, log_record):
        """Test redaction of exception text."""
        log_record.exc_text = "ValueError: Invalid API_KEY=sk_test_abc123"
        log_filter.filter(log_record)
        assert "sk_test_abc123" not in log_record.exc_text
        assert "API_KEY=***REDACTED***" in log_record.exc_text

    def test_preserve_normal_text(self, log_filter, log_record):
        """Test that normal text is not redacted."""
        log_record.msg = "Processing job abc123 for user john@example.com"
        original_msg = log_record.msg
        log_filter.filter(log_record)
        assert log_record.msg == original_msg

    def test_multiple_secrets_in_one_message(self, log_filter, log_record):
        """Test redaction of multiple secrets in single message."""
        log_record.msg = (
            "Config loaded: GOOGLE_API_KEY=abc123 and "
            "ASSEMBLYAI_API_KEY=xyz789 with "
            "WEBHOOK_SECRET_TOKEN=secret123"
        )
        log_filter.filter(log_record)
        assert "abc123" not in log_record.msg
        assert "xyz789" not in log_record.msg
        assert "secret123" not in log_record.msg
        assert log_record.msg.count("***REDACTED***") == 3

    def test_filter_always_returns_true(self, log_filter, log_record):
        """Test that filter always returns True (passes record)."""
        log_record.msg = "Test message with api_key=secret123"
        result = log_filter.filter(log_record)
        assert result is True

    def test_case_insensitive_patterns(self, log_filter, log_record):
        """Test that patterns are case-insensitive."""
        test_cases = [
            "API_KEY=secret123",
            "api_key=secret123",
            "Api_Key=secret123",
            "authorization: Bearer token123",
            "Authorization: Bearer token123",
            "AUTHORIZATION: Bearer token123",
        ]
        for test_msg in test_cases:
            log_record.msg = test_msg
            log_filter.filter(log_record)
            assert "***REDACTED***" in log_record.msg
