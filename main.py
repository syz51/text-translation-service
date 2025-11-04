"""FastAPI service for translating SRT subtitle files using OpenRouter."""

import os
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

from srt_parser import parse_srt, reconstruct_srt, extract_texts, update_texts
from openrouter_client import translate_batch, OpenRouterError

# Load environment variables
load_dotenv()

# Get API key from environment (optional)
SERVICE_API_KEY = os.getenv("API_KEY")

# Initialize FastAPI app
app = FastAPI(
    title="Text Translation Service",
    description="Translate SRT subtitle files using OpenRouter's Claude models",
    version="0.1.0",
)


# Authentication middleware
@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    """Middleware to validate API key if configured.

    If SERVICE_API_KEY is set in environment, validates X-API-Key header.
    If not set, authentication is disabled.
    """
    # Skip auth for health check and docs endpoints
    if request.url.path in ["/", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    # Only enforce auth if API_KEY is configured
    if SERVICE_API_KEY:
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Missing X-API-Key header. Please provide API key for authentication."
                },
            )

        if api_key != SERVICE_API_KEY:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid API key. Please check your X-API-Key header."
                },
            )

    return await call_next(request)


# Request/Response models
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
    source_language: Optional[str] = Field(
        None, description="Optional source language hint"
    )
    country: Optional[str] = Field(
        None,
        description="Optional target country/region for localization (e.g., 'Brazil', 'Spain', 'Mexico')",
    )
    model: Optional[str] = Field(
        None,
        description="Optional OpenRouter model override (default: anthropic/claude-sonnet-4)",
    )


class TranslationResponse(BaseModel):
    """Response model for translation endpoint."""

    translated_srt: str = Field(
        ..., description="Translated SRT subtitle content with preserved timestamps"
    )
    entry_count: int = Field(..., description="Number of subtitle entries translated")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Text Translation Service",
        "status": "running",
        "version": "0.1.0",
        "authentication": "enabled" if SERVICE_API_KEY else "disabled",
    }


@app.post(
    "/translate",
    response_model=TranslationResponse,
    status_code=status.HTTP_200_OK,
    summary="Translate SRT subtitle file",
    description="Translates SRT subtitle content while preserving timestamps and structure",
)
async def translate_srt(request: TranslationRequest):
    """Translate SRT subtitle file to target language.

    Args:
        request: Translation request with SRT content and target language

    Returns:
        Translated SRT content with preserved timestamps

    Raises:
        HTTPException: If parsing or translation fails
    """
    try:
        # Parse SRT content
        entries = parse_srt(request.srt_content)

        if not entries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid SRT entries found in content. Please check SRT format.",
            )

        # Extract texts for translation
        texts = extract_texts(entries)

        # Prepare translation parameters
        translate_params = {
            "target_language": request.target_language,
            "source_language": request.source_language,
            "country": request.country,
        }
        if request.model:
            translate_params["model"] = request.model

        # Translate all texts concurrently
        translated_texts = await translate_batch(texts, **translate_params)

        # Update entries with translated texts
        translated_entries = update_texts(entries, translated_texts)

        # Reconstruct SRT format
        translated_srt = reconstruct_srt(translated_entries)

        return TranslationResponse(
            translated_srt=translated_srt, entry_count=len(entries)
        )

    except ValueError as e:
        # SRT parsing or validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid SRT format: {str(e)}",
        )
    except OpenRouterError as e:
        # OpenRouter API errors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Translation service error: {str(e)}",
        )
    except Exception as e:
        # Unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
