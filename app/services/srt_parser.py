"""SRT subtitle file parser and reconstructor using pysubs2.

Handles parsing SRT format files, extracting text for translation,
and reconstructing the SRT format with translated text while preserving
timestamps and structure.
"""

import pysubs2

from app.models.srt import SRTEntry


def _ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _srt_time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp to milliseconds."""
    # Format: HH:MM:SS,mmm
    time_part, ms_part = time_str.split(",")
    hours, minutes, seconds = map(int, time_part.split(":"))
    milliseconds = int(ms_part)

    total_ms = hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds
    return total_ms


def parse_srt(content: str) -> list[SRTEntry]:
    """Parse SRT content into a list of subtitle entries.

    Args:
        content: Raw SRT file content as string

    Returns:
        List of SRTEntry objects with index, timestamps, and text

    Raises:
        ValueError: If SRT format is invalid
    """
    if not content or not content.strip():
        raise ValueError("SRT content is empty")

    try:
        subs = pysubs2.SSAFile.from_string(content, format_="srt")
    except Exception as e:
        raise ValueError(f"Failed to parse SRT: {e}")

    entries = []
    for i, line in enumerate(subs, start=1):
        start_time = _ms_to_srt_time(line.start)
        end_time = _ms_to_srt_time(line.end)
        entries.append(SRTEntry(i, start_time, end_time, line.text))

    return entries


def reconstruct_srt(entries: list[SRTEntry]) -> str:
    """Reconstruct SRT format from list of entries.

    Args:
        entries: List of SRTEntry objects

    Returns:
        SRT formatted string
    """
    subs = pysubs2.SSAFile()

    for entry in entries:
        # Convert SRT time format back to milliseconds
        start_ms = _srt_time_to_ms(entry.start_time)
        end_ms = _srt_time_to_ms(entry.end_time)

        event = pysubs2.SSAEvent(start=start_ms, end=end_ms, text=entry.text)
        subs.append(event)

    return subs.to_string("srt")


def extract_texts(entries: list[SRTEntry]) -> list[str]:
    """Extract just the text content from entries.

    Args:
        entries: List of SRTEntry objects

    Returns:
        List of text strings
    """
    return [entry.text for entry in entries]


def update_texts(entries: list[SRTEntry], translated_texts: list[str]) -> list[SRTEntry]:
    """Update entry texts with translations.

    Args:
        entries: Original list of SRTEntry objects
        translated_texts: List of translated text strings (same length as entries)

    Returns:
        List of SRTEntry objects with updated texts

    Raises:
        ValueError: If lengths don't match
    """
    if len(entries) != len(translated_texts):
        raise ValueError(
            f"Mismatch: {len(entries)} entries but {len(translated_texts)} translations"
        )

    updated_entries = []
    for entry, translated_text in zip(entries, translated_texts):
        updated_entry = SRTEntry(entry.index, entry.start_time, entry.end_time, translated_text)
        updated_entries.append(updated_entry)

    return updated_entries
