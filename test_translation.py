"""Test script for SRT translation."""

import asyncio
from pathlib import Path
from srt_parser import parse_srt, extract_texts, update_texts, reconstruct_srt
from google_genai_client import translate_batch


async def main():
    """Run translation test on test.srt file."""
    # Read test.srt
    test_file = Path("test.srt")
    print(f"Reading {test_file}...")
    srt_content = test_file.read_text(encoding="utf-8")

    # Parse SRT
    print("Parsing SRT entries...")
    entries = parse_srt(srt_content)
    print(f"Found {len(entries)} subtitle entries")

    # Extract texts
    texts = extract_texts(entries)
    print("\nFirst 3 entries (original):")
    for i, text in enumerate(texts[:3], 1):
        print(f"  {i}. {text[:50]}...")

    # Translate
    target_language = input(
        "\nTarget language (e.g., Spanish, French, Japanese): "
    ).strip()
    if not target_language:
        target_language = "Spanish"
        print(f"Using default: {target_language}")

    chunk_size_input = input(
        "\nChunk size (entries per request, 1-20, default 8): "
    ).strip()
    chunk_size = 8
    if chunk_size_input:
        try:
            chunk_size = max(1, min(20, int(chunk_size_input)))
        except ValueError:
            pass
    print(f"Using chunk size: {chunk_size}")

    print(
        f"\nTranslating to {target_language} (grouping {chunk_size} entries per request)..."
    )
    translated_texts = await translate_batch(
        texts,
        target_language=target_language,
        max_concurrent=3,  # Limit concurrent requests
        chunk_size=chunk_size,
    )

    print("\nFirst 3 entries (translated):")
    for i, text in enumerate(translated_texts[:3], 1):
        print(f"  {i}. {text[:50]}...")

    # Reconstruct SRT
    translated_entries = update_texts(entries, translated_texts)
    translated_srt = reconstruct_srt(translated_entries)

    # Save output
    output_file = Path(
        f"test_translated_{target_language.lower().replace(' ', '_')}.srt"
    )
    output_file.write_text(translated_srt, encoding="utf-8")
    print(f"\n✓ Translated SRT saved to: {output_file}")
    print(f"  Total entries: {len(entries)}")


if __name__ == "__main__":
    asyncio.run(main())
