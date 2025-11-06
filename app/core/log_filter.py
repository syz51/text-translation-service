"""Logging filter for redacting sensitive data from log messages."""

import logging
import re
from typing import Pattern


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log messages.

    Redacts:
    - API keys (Google, AssemblyAI, service auth)
    - Tokens (webhook secrets, auth tokens)
    - S3 credentials and presigned URLs
    - Authorization headers
    """

    def __init__(self):
        """Initialize filter with redaction patterns."""
        super().__init__()

        # Compile patterns once for performance
        # Order matters - more specific patterns should come first
        self.patterns: list[tuple[Pattern, str]] = [
            # Authorization headers with Bearer tokens (must come before generic Bearer pattern)
            (
                re.compile(r"(?i)(Authorization):\s+(Bearer\s+)?([^\s,]+)", re.IGNORECASE),
                r"\1: ***REDACTED***",
            ),
            # X-API-Key headers
            (
                re.compile(r"(?i)(X-API-Key):\s*([^\s,]+)", re.IGNORECASE),
                r"\1: ***REDACTED***",
            ),
            # Environment variable assignments (e.g., GOOGLE_API_KEY=abc123)
            (
                re.compile(
                    r"(?i)(GOOGLE_API_KEY|ASSEMBLYAI_API_KEY|API_KEY|WEBHOOK_SECRET_TOKEN|S3_SECRET_ACCESS_KEY|S3_ACCESS_KEY_ID)=([^\s,\)]+)"
                ),
                r"\1=***REDACTED***",
            ),
            # API keys and tokens with key=value format
            (
                re.compile(
                    r"(?i)(api[_-]?key|apikey|key|token|secret|password|credential)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{20,})",
                    re.IGNORECASE,
                ),
                r"\1=***REDACTED***",
            ),
            # Presigned URLs with AWS signatures (redact query params after ?)
            (
                re.compile(
                    r"(https?://[^\s\?]+\.s3[^\s]*\?)([^\s]+)",
                    re.IGNORECASE,
                ),
                r"\1***REDACTED***",
            ),
            # Webhook URLs with secret tokens in path
            (
                re.compile(
                    r"(/webhooks/assemblyai/)([a-zA-Z0-9_\-\.]{10,})",
                    re.IGNORECASE,
                ),
                r"\1***REDACTED***",
            ),
            # Bearer tokens (standalone, not in Authorization header)
            (
                re.compile(r"\bBearer\s+([A-Za-z0-9_\-\.=]+)", re.IGNORECASE),
                r"Bearer ***REDACTED***",
            ),
            # Standalone API keys with common prefixes (sk_, AIza, etc.)
            (
                re.compile(r"\b(sk_[a-z]+_[A-Za-z0-9]{15,}|AIza[A-Za-z0-9_\-]{15,})\b", re.IGNORECASE),
                r"***REDACTED***",
            ),
            # Generic long alphanumeric strings that look like secrets (32+ chars)
            # Only if preceded by common secret indicators
            (
                re.compile(
                    r"(?i)(secret|token|key|password|credential)[\s:=]+['\"]?([A-Za-z0-9_\-\.]{32,})",
                    re.IGNORECASE,
                ),
                r"\1 ***REDACTED***",
            ),
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record by redacting sensitive data.

        Args:
            record: Log record to filter

        Returns:
            True (always pass the record after redaction)
        """
        # Redact message
        if record.msg:
            record.msg = self.redact(str(record.msg))

        # Redact args (used in % formatting)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)

        # Redact exception info if present
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)

        return True

    def _redact_value(self, value):
        """Redact a single value, preserving type for non-strings.

        Args:
            value: Value to potentially redact

        Returns:
            Redacted value if string, original value otherwise
        """
        # Only redact string values to preserve numeric types for formatting
        if isinstance(value, str):
            return self.redact(value)
        return value

    def redact(self, text: str) -> str:
        """Apply redaction patterns to text.

        Args:
            text: Text to redact

        Returns:
            Text with sensitive data redacted
        """
        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return text
