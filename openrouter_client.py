"""OpenRouter API client for text translation using Claude models."""

import os
from typing import Optional
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenRouter API configuration
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"  # Latest Claude Sonnet model


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors."""

    pass


async def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 300.0,
    country: Optional[str] = None,
) -> str:
    """Translate text using OpenRouter's Claude model with extended thinking.

    Args:
        text: Text to translate (individual subtitle entry)
        target_language: Target language (e.g., "Spanish", "French", "Japanese")
        source_language: Optional source language hint
        model: OpenRouter model ID (default: anthropic/claude-sonnet-4.5)
        timeout: Request timeout in seconds (default: 300s / 5min per entry)
        country: Optional target country/region for localization

    Returns:
        Translated text

    Raises:
        OpenRouterError: If API request fails or returns error
        ValueError: If API key not configured
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY not found in environment. "
            "Please set it in .env file or environment variables."
        )

    # Build enhanced prompt for subtitle translation
    source_lang = source_language if source_language else "the source language"
    target_country = country if country else target_language

    user_prompt = f"""Translate the following subtitle text from {source_lang} to {target_language} for {target_country} audience.

<SOURCE_TEXT>
{text}
</SOURCE_TEXT>

Please consider the following when translating:

Step 1: Context Analysis
- Identify text type (dialogue/narration/UI), domain, and audience
- Note cultural elements, idioms, slang, or technical terms
- Determine appropriate register, tone, and formality level

Step 2: Translation Challenges
- List phrases/concepts difficult to translate
- Consider multiple options for key terms/idioms
- Identify where cultural adaptation needed (names, references, humor)

Step 3: Subtitle Constraints
- Keep translations concise for reading speed (subtitles are time-constrained)
- Preserve line breaks for subtitle display formatting
- Use natural spoken language (avoid overly formal/literary style)
- Ensure character limits appropriate for subtitle display

Step 4: Initial Translation
- Create first translation attempt
- Maintain terminology consistency
- Preserve original meaning, tone, and emotional impact

Step 5: Self-Critique
Review for:
(i) Accuracy: No mistranslation, omission, or untranslated text
(ii) Fluency: Natural {target_language} grammar, flow, and readability
(iii) Style: Match source tone (casual/formal/emotional)
(iv) Timing: Concise enough for subtitle reading speed
(v) Cultural fit: Appropriate for {target_country} audience
(vi) Line breaks: Preserved exactly as in source

Step 6: Final Translation
- Apply critique for improved translation
- Address all identified issues

CRITICAL: Output ONLY the final translated text. No explanations, labels, or extra formatting. Preserve line breaks exactly."""

    # Prepare API request
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Text Translation Service",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 200000,
        "temperature": 0.5,
        # "reasoning": {
        #     "max_tokens": 8192,
        #     "exclude": True,
        #     "enabled": True,
        # },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{OPENROUTER_API_BASE}/chat/completions", headers=headers, json=payload
            )

            # Check for HTTP errors
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get(
                        "message", error_detail
                    )
                except Exception:
                    pass
                raise OpenRouterError(
                    f"OpenRouter API error (status {response.status_code}): {error_detail}"
                )

            # Parse response
            result = response.json()

            # Extract translated text from response
            if "choices" not in result or len(result["choices"]) == 0:
                raise OpenRouterError("No translation returned from API")

            translated_text = result["choices"][0]["message"]["content"]

            return translated_text.strip()

    except httpx.TimeoutException:
        raise OpenRouterError(f"Translation request timed out after {timeout} seconds")
    except httpx.RequestError as e:
        raise OpenRouterError(f"Network error during translation: {str(e)}")
    except Exception as e:
        if isinstance(e, OpenRouterError):
            raise
        raise OpenRouterError(f"Unexpected error during translation: {str(e)}")


async def translate_batch(
    texts: list[str],
    target_language: str,
    source_language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_concurrent: int = 100,
    country: Optional[str] = None,
) -> list[str]:
    """Translate multiple texts concurrently.

    Args:
        texts: List of texts to translate
        target_language: Target language
        source_language: Optional source language hint
        model: OpenRouter model ID
        max_concurrent: Maximum number of concurrent requests
        country: Optional target country/region for localization

    Returns:
        List of translated texts in same order as input

    Raises:
        OpenRouterError: If any translation fails
    """
    import asyncio

    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    async def translate_with_semaphore(text: str) -> str:
        async with semaphore:
            return await translate_text(
                text, target_language, source_language, model, country=country
            )

    # Execute translations concurrently
    tasks = [translate_with_semaphore(text) for text in texts]
    translations = await asyncio.gather(*tasks)

    return translations
