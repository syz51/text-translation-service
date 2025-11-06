"""Pydantic schemas for translation API."""

from pydantic import BaseModel, Field


class TranslationRequest(BaseModel):
    """Request model for translation endpoint."""

    srt_content: str = Field(
        ..., description="SRT subtitle file content to translate", min_length=1
    )
    target_language: str = Field(
        ...,
        description="Target language for translation (e.g., 'Spanish', 'French', 'Japanese')",
        min_length=1,
    )
    source_language: str | None = Field(None, description="Optional source language hint")
    country: str | None = Field(
        None,
        description=(
            "Optional target country/region for localization (e.g., 'Brazil', 'Spain', 'Mexico')"
        ),
    )
    model: str | None = Field(
        None,
        description="Optional Google GenAI model override (default: gemini-2.5-pro)",
    )
    chunk_size: int | None = Field(
        100,
        description="Number of consecutive entries to translate together (default: 100)",
    )


class TranslationResponse(BaseModel):
    """Response model for translation endpoint."""

    translated_srt: str = Field(
        ..., description="Translated SRT subtitle content with preserved timestamps"
    )
    entry_count: int = Field(..., description="Number of subtitle entries translated")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    service: str
    status: str
    version: str
    authentication: str
