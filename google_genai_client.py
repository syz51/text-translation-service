"""Google GenAI client for text translation using Gemini models with thinking enabled."""

import os
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google GenAI configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEFAULT_MODEL = "gemini-2.5-pro"


class GoogleGenAIError(Exception):
    """Custom exception for Google GenAI API errors."""

    pass


async def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    # timeout: float = 300.0,
    country: Optional[str] = None,
) -> str:
    """Translate text using Google GenAI's Gemini model with extended thinking.

    Args:
        text: Text to translate (individual subtitle entry)
        target_language: Target language (e.g., "Spanish", "French", "Japanese")
        source_language: Optional source language hint
        model: Google GenAI model ID (default: gemini-2.5-pro)
        timeout: Request timeout in seconds (default: 300s / 5min per entry)
        country: Optional target country/region for localization

    Returns:
        Translated text

    Raises:
        GoogleGenAIError: If API request fails or returns error
        ValueError: If API key not configured
    """
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. "
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

    try:
        # Initialize client
        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Generate content with thinking enabled
        response = client.models.generate_content(
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

        # Extract translated text from response (filter out thoughts)
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
    source_language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_concurrent: int = 25,
    country: Optional[str] = None,
    chunk_size: int = 8,
) -> list[str]:
    """Translate multiple texts in chunks for better context.

    Args:
        texts: List of texts to translate
        target_language: Target language
        source_language: Optional source language hint
        model: Google GenAI model ID
        max_concurrent: Maximum number of concurrent requests
        country: Optional target country/region for localization
        chunk_size: Number of entries to group together (default: 8)

    Returns:
        List of translated texts in same order as input

    Raises:
        GoogleGenAIError: If any translation fails
    """
    import asyncio

    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    async def translate_chunk_with_semaphore(chunk: list[str]) -> list[str]:
        async with semaphore:
            return await translate_text_chunk(
                chunk, target_language, source_language, model, country=country
            )

    # Group texts into chunks
    chunks = [texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)]

    # Execute chunk translations concurrently
    tasks = [translate_chunk_with_semaphore(chunk) for chunk in chunks]
    translated_chunks = await asyncio.gather(*tasks)

    # Flatten results
    return [text for chunk in translated_chunks for text in chunk]


async def translate_text_chunk(
    texts: list[str],
    target_language: str,
    source_language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    # timeout: float = 300.0,
    country: Optional[str] = None,
) -> list[str]:
    """Translate chunk of subtitle entries together for better context.

    Args:
        texts: List of consecutive subtitle texts to translate together
        target_language: Target language
        source_language: Optional source language hint
        model: Google GenAI model ID
        timeout: Request timeout in seconds
        country: Optional target country/region for localization

    Returns:
        List of translated texts in same order

    Raises:
        GoogleGenAIError: If API request fails or parsing fails
    """
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. "
            "Please set it in .env file or environment variables."
        )

    # Format multiple entries with delimiters
    formatted_entries = []
    for i, text in enumerate(texts, start=1):
        formatted_entries.append(f"[ENTRY_{i}]\n{text}\n[/ENTRY_{i}]")

    combined_text = "\n\n".join(formatted_entries)

    source_lang = source_language if source_language else "the source language"
    target_country = country if country else target_language

    user_prompt = f"""Translate the following {len(texts)} consecutive subtitle entries from {source_lang} to {target_language} for {target_country} audience.

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
You MUST output exactly {len(texts)} entries using the same delimiters:
[ENTRY_1]
translated text for entry 1
[/ENTRY_1]

[ENTRY_2]
translated text for entry 2
[/ENTRY_2]

...and so on. Output ONLY the delimited entries. No explanations, labels, or extra text. Preserve line breaks within entries exactly."""

    try:
        # Initialize client
        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Generate content with thinking enabled
        response = client.models.generate_content(
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

        # Extract translated text from response (filter out thoughts)
        translated_parts = [
            part.text
            for part in response.candidates[0].content.parts
            if part.text and not part.thought
        ]

        if not translated_parts:
            raise GoogleGenAIError("No translation returned from API")

        translated_text = "".join(translated_parts).strip()

        # Parse out individual entries
        import re

        parsed_entries = []
        for i in range(1, len(texts) + 1):
            pattern = rf"\[ENTRY_{i}\](.*?)\[/ENTRY_{i}\]"
            match = re.search(pattern, translated_text, re.DOTALL)
            if match:
                parsed_entries.append(match.group(1).strip())
            else:
                raise GoogleGenAIError(f"Failed to parse ENTRY_{i} from response")

        if len(parsed_entries) != len(texts):
            raise GoogleGenAIError(
                f"Expected {len(texts)} entries, got {len(parsed_entries)}"
            )

        return parsed_entries

    except Exception as e:
        if isinstance(e, GoogleGenAIError):
            raise
        raise GoogleGenAIError(f"Error during chunk translation: {str(e)}")
