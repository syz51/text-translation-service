"""Translation endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import TranslationRequest, TranslationResponse
from app.services.srt_parser import extract_texts, parse_srt, reconstruct_srt, update_texts
from app.services.translation import GoogleGenAIError, translate_batch

router = APIRouter()


@router.post(
    "",
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
            "chunk_size": request.chunk_size,
        }
        if request.model:
            translate_params["model"] = request.model

        # Translate texts in chunks for better context
        translated_texts = await translate_batch(texts, **translate_params)

        # Update entries with translated texts
        translated_entries = update_texts(entries, translated_texts)

        # Reconstruct SRT format
        translated_srt = reconstruct_srt(translated_entries)

        return TranslationResponse(translated_srt=translated_srt, entry_count=len(entries))

    except ValueError as e:
        # SRT parsing or validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid SRT format: {str(e)}",
        )
    except GoogleGenAIError as e:
        # Google GenAI API errors
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
