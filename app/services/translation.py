"""Google GenAI translation service using Gemini models with thinking enabled."""

import asyncio
import re
import uuid

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GoogleGenAIError(Exception):
    """Custom exception for Google GenAI API errors."""

    pass


async def translate_text(
    text: str,
    target_language: str,
    source_language: str | None = None,
    model: str | None = None,
    country: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Translate text using Google GenAI's Gemini model with extended thinking.

    Args:
        text: Text to translate (individual subtitle entry)
        target_language: Target language (e.g., "Spanish", "French", "Japanese")
        source_language: Optional source language hint
        model: Google GenAI model ID (default from settings)
        country: Optional target country/region for localization
        settings: Settings instance (optional, will use get_settings() if not provided)

    Returns:
        Translated text

    Raises:
        GoogleGenAIError: If API request fails or returns error
        ValueError: If API key not configured
    """
    if settings is None:
        settings = get_settings()

    if not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. "
            "Please set it in .env file or environment variables."
        )

    model = model or settings.default_model
    source_lang = source_language if source_language else "the source language"
    target_country = country if country else target_language

    user_prompt = f"""Translate the following subtitle text from {source_lang} to \
{target_language} for {target_country} audience.

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

CRITICAL: Output ONLY the final translated text. No explanations, labels, or extra
formatting. Preserve line breaks exactly."""

    try:
        client = genai.Client(api_key=settings.google_api_key)

        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=65536,
                top_p=0.95,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=32768,
                ),
            ),
        )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise GoogleGenAIError("Invalid response structure from API")

        translated_parts = [
            part.text
            for part in response.candidates[0].content.parts
            if part.text and not part.thought
        ]

        if not translated_parts:
            raise GoogleGenAIError("No translation returned from API")

        return "".join(translated_parts).strip()

    except Exception as e:
        if isinstance(e, GoogleGenAIError):
            raise
        raise GoogleGenAIError(f"Error during translation: {str(e)}")


async def translate_batch(
    texts: list[str],
    target_language: str,
    source_language: str | None = None,
    model: str | None = None,
    max_concurrent: int | None = None,
    country: str | None = None,
    chunk_size: int | None = None,
    settings: Settings | None = None,
) -> list[str]:
    """Translate multiple texts in chunks for better context.

    Args:
        texts: List of texts to translate
        target_language: Target language
        source_language: Optional source language hint
        model: Google GenAI model ID
        max_concurrent: Maximum number of concurrent requests
        country: Optional target country/region for localization
        chunk_size: Number of entries to group together
        settings: Settings instance (optional, will use get_settings() if not provided)

    Returns:
        List of translated texts in same order as input

    Raises:
        GoogleGenAIError: If any translation fails
    """
    if settings is None:
        settings = get_settings()

    model = model or settings.default_model
    max_concurrent = max_concurrent or settings.max_concurrent_requests
    chunk_size = chunk_size or settings.default_chunk_size

    chunks = [texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)]
    total_chunks = len(chunks)

    logger.info(
        "Starting translation: %d entries -> %d chunks (chunk_size=%d, max_concurrent=%d)",
        len(texts),
        total_chunks,
        chunk_size,
        max_concurrent,
    )

    completed_chunks = 0
    completed_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def translate_chunk_with_semaphore(chunk_idx: int, chunk: list[str]) -> list[str]:
        nonlocal completed_chunks
        async with semaphore:
            chunk_start_idx = chunk_idx * chunk_size + 1
            chunk_end_idx = chunk_start_idx + len(chunk) - 1

            result = await translate_text_chunk(
                chunk,
                target_language,
                source_language,
                model,
                country=country,
                chunk_idx=chunk_idx + 1,
                total_chunks=total_chunks,
                settings=settings,
            )

            async with completed_lock:
                completed_chunks += 1
                logger.info(
                    "Chunk %d/%d complete (entries %d-%d)",
                    completed_chunks,
                    total_chunks,
                    chunk_start_idx,
                    chunk_end_idx,
                )

            return result

    tasks = [translate_chunk_with_semaphore(i, chunk) for i, chunk in enumerate(chunks)]
    translated_chunks = await asyncio.gather(*tasks)

    logger.info("Translation complete: %d entries translated", len(texts))

    return [text for chunk in translated_chunks for text in chunk]


async def translate_text_chunk(
    texts: list[str],
    target_language: str,
    source_language: str | None = None,
    model: str | None = None,
    country: str | None = None,
    chunk_idx: int | None = None,
    total_chunks: int | None = None,
    settings: Settings | None = None,
) -> list[str]:
    """Translate chunk of subtitle entries together for better context.

    Args:
        texts: List of consecutive subtitle texts to translate together
        target_language: Target language
        source_language: Optional source language hint
        model: Google GenAI model ID
        country: Optional target country/region for localization
        chunk_idx: Optional chunk index for logging
        total_chunks: Optional total chunks for logging
        settings: Settings instance (optional, will use get_settings() if not provided)

    Returns:
        List of translated texts in same order

    Raises:
        GoogleGenAIError: If API request fails or parsing fails
    """
    if settings is None:
        settings = get_settings()

    if not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. "
            "Please set it in .env file or environment variables."
        )

    model = model or settings.default_model

    if chunk_idx and total_chunks:
        logger.info("Processing chunk %d/%d (%d entries)", chunk_idx, total_chunks, len(texts))

    session_id = uuid.uuid4().hex[:8]

    formatted_entries = []
    for i, text in enumerate(texts, start=1):
        formatted_entries.append(f"[ENTRY_{i}_{session_id}]\n{text}\n[/ENTRY_{i}_{session_id}]")

    combined_text = "\n\n".join(formatted_entries)

    source_lang = source_language if source_language else "the source language"
    target_country = country if country else target_language

    user_prompt = f"""Translate the following {len(texts)} consecutive subtitle \
entries from {source_lang} to {target_language} for {target_country} audience.

<SOURCE_TEXT>
{combined_text}
</SOURCE_TEXT>

Please consider the following when translating:

Step 1: Context Analysis
- These are consecutive subtitle entries - consider dialogue flow and context between entries
- Identify text type (dialogue/narration/UI), domain, and audience
- Note cultural elements, idioms, slang, or technical terms
- Determine appropriate register, tone, and formality level

Step 2: Translation Challenges
- List phrases/concepts difficult to translate
- Consider multiple options for key terms/idioms
- Identify where cultural adaptation needed (names, references, humor)
- Maintain consistency for recurring terms/names across all entries

Step 3: Subtitle Constraints
- Keep translations concise for reading speed (subtitles are time-constrained)
- Preserve line breaks within each entry for subtitle display formatting
- Use natural spoken language (avoid overly formal/literary style)
- Ensure character limits appropriate for subtitle display

Step 4: Initial Translation
- Translate all entries considering the dialogue flow and context
- Maintain terminology consistency across entries
- Preserve original meaning, tone, and emotional impact

Step 5: Self-Critique
Review for:
(i) Accuracy: No mistranslation, omission, or untranslated text
(ii) Fluency: Natural {target_language} grammar, flow, and readability
(iii) Style: Match source tone (casual/formal/emotional)
(iv) Timing: Concise enough for subtitle reading speed
(v) Cultural fit: Appropriate for {target_country} audience
(vi) Context: Translations work together as continuous dialogue
(vii) Line breaks: Preserved exactly as in source for each entry

Step 6: Final Translation
- Apply critique for improved translation
- Address all identified issues

CRITICAL OUTPUT FORMAT:
You MUST output exactly {len(texts)} entries using the EXACT same delimiters:
[ENTRY_1_{session_id}]
translated text for entry 1
[/ENTRY_1_{session_id}]

[ENTRY_2_{session_id}]
translated text for entry 2
[/ENTRY_2_{session_id}]

...and so on. Output ONLY the delimited entries. No explanations, labels, or
extra text. Preserve line breaks within entries exactly."""

    try:
        client = genai.Client(api_key=settings.google_api_key)

        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=65536,
                top_p=0.95,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=32768,
                ),
            ),
        )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise GoogleGenAIError("Invalid response structure from API")

        translated_parts = [
            part.text
            for part in response.candidates[0].content.parts
            if part.text and not part.thought
        ]

        if not translated_parts:
            raise GoogleGenAIError("No translation returned from API")

        translated_text = "".join(translated_parts).strip()

        # Parse out individual entries
        matches_with_pos = []
        missing_entries = []
        duplicate_entries = []

        for i in range(1, len(texts) + 1):
            pattern = rf"\[\s*ENTRY_{i}_{session_id}\s*\](.*?)\[\s*/ENTRY_{i}_{session_id}\s*\]"
            matches = list(re.finditer(pattern, translated_text, re.DOTALL | re.IGNORECASE))

            if len(matches) > 1:
                duplicate_entries.append(i)
                content = matches[0].group(1)
                matches_with_pos.append((i, matches[0].start(), content))
            elif len(matches) == 1:
                content = matches[0].group(1)
                matches_with_pos.append((i, matches[0].start(), content))
            else:
                fallback_pattern = (
                    rf"\[\s*ENTRY_{i}(?:_[a-f0-9]{{8}})?\s*\](.*?)"
                    rf"\[\s*/ENTRY_{i}(?:_[a-f0-9]{{8}})?\s*\]"
                )
                fallback_matches = list(
                    re.finditer(fallback_pattern, translated_text, re.DOTALL | re.IGNORECASE)
                )

                if len(fallback_matches) > 1:
                    duplicate_entries.append(i)
                    content = fallback_matches[0].group(1)
                    matches_with_pos.append((i, fallback_matches[0].start(), content))
                elif len(fallback_matches) == 1:
                    content = fallback_matches[0].group(1)
                    matches_with_pos.append((i, fallback_matches[0].start(), content))
                else:
                    missing_entries.append(i)

        if missing_entries:
            error_msg = f"Failed to parse entries: {missing_entries}. "
            error_msg += f"Response preview: {translated_text[:500]}..."
            raise GoogleGenAIError(error_msg)

        if duplicate_entries:
            error_msg = f"Duplicate entries detected: {duplicate_entries}. Using first occurrence. "
            error_msg += f"Response preview: {translated_text[:500]}..."
            raise GoogleGenAIError(error_msg)

        sorted_matches = sorted(matches_with_pos, key=lambda x: x[1])
        expected_order = list(range(1, len(texts) + 1))
        actual_order = [m[0] for m in sorted_matches]

        if actual_order != expected_order:
            raise GoogleGenAIError(
                f"Entries are reordered in response. Expected: {expected_order}, "
                f"Got: {actual_order}"
            )

        parsed_entries = []
        for entry_num, _, content in sorted_matches:
            # Strip all leading and trailing whitespace (newlines, spaces, etc.)
            normalized = content.strip()

            delimiter_check = r"\[\s*(?:/)?ENTRY_\d+(?:_[a-f0-9]{8})?\s*\]"
            if re.search(delimiter_check, normalized, re.IGNORECASE):
                raise GoogleGenAIError(
                    f"Entry {entry_num} contains delimiter-like content: {normalized[:100]}..."
                )

            parsed_entries.append(normalized)

        if len(parsed_entries) != len(texts):
            raise GoogleGenAIError(
                f"Expected {len(texts)} entries, got {len(parsed_entries)}. "
                f"Missing: {len(texts) - len(parsed_entries)}"
            )

        return parsed_entries

    except Exception as e:
        if isinstance(e, GoogleGenAIError):
            raise
        raise GoogleGenAIError(f"Error during chunk translation: {str(e)}")
