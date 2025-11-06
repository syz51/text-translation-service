"""Tests for SRT parser service."""

import pytest

from app.models.srt import SRTEntry
from app.services.srt_parser import extract_texts, parse_srt, reconstruct_srt, update_texts


class TestParseSrt:
    """Tests for parse_srt function."""

    def test_parse_srt_valid(self):
        """Test parsing valid SRT content."""
        content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?"""

        entries = parse_srt(content)
        assert len(entries) == 2
        assert entries[0].text == "Hello world"
        assert entries[1].text == "How are you?"

    def test_parse_srt_invalid(self):
        """Test parsing invalid SRT content."""
        with pytest.raises(ValueError):
            parse_srt("")  # Empty content should raise ValueError

    def test_parse_srt_whitespace_only(self):
        """Test parsing SRT with only whitespace raises ValueError."""
        with pytest.raises(ValueError, match="SRT content is empty"):
            parse_srt("   \n\n  \t  ")

    def test_parse_srt_multiline_entry(self):
        """Test parsing SRT with multiline text entries."""
        content = """1
00:00:01,000 --> 00:00:04,000
First line
Second line
Third line

2
00:00:05,000 --> 00:00:08,000
Another entry"""

        entries = parse_srt(content)
        assert len(entries) == 2
        assert "First line" in entries[0].text
        assert "Second line" in entries[0].text
        assert "Third line" in entries[0].text
        assert entries[1].text == "Another entry"

    def test_parse_srt_unicode_and_special_chars(self):
        """Test parsing SRT with Unicode and special characters."""
        content = """1
00:00:01,000 --> 00:00:04,000
Hello! 你好 مرحبا 😊

2
00:00:05,000 --> 00:00:08,000
Special: "quotes" 'apostrophes' <tags> & symbols"""

        entries = parse_srt(content)
        assert len(entries) == 2
        assert "你好" in entries[0].text
        assert "😊" in entries[0].text
        assert '"quotes"' in entries[1].text

    def test_parse_srt_edge_timestamps(self):
        """Test parsing SRT with edge case timestamps."""
        content = """1
00:00:00,000 --> 00:00:01,000
Start

2
01:30:45,999 --> 01:30:50,000
End"""

        entries = parse_srt(content)
        assert len(entries) == 2
        assert entries[0].start_time == "00:00:00,000"
        assert entries[0].end_time == "00:00:01,000"
        assert entries[1].start_time == "01:30:45,999"


class TestExtractTexts:
    """Tests for extract_texts function."""

    def test_extract_texts(self):
        """Test extracting texts from entries."""
        entries = [
            SRTEntry(1, "00:00:01,000", "00:00:04,000", "Hello"),
            SRTEntry(2, "00:00:05,000", "00:00:08,000", "World"),
        ]
        texts = extract_texts(entries)
        assert texts == ["Hello", "World"]


class TestUpdateTexts:
    """Tests for update_texts function."""

    def test_update_texts(self):
        """Test updating entry texts."""
        entries = [
            SRTEntry(1, "00:00:01,000", "00:00:04,000", "Hello"),
            SRTEntry(2, "00:00:05,000", "00:00:08,000", "World"),
        ]
        translated = ["Hola", "Mundo"]
        updated = update_texts(entries, translated)

        assert len(updated) == 2
        assert updated[0].text == "Hola"
        assert updated[1].text == "Mundo"
        assert updated[0].start_time == "00:00:01,000"

    def test_update_texts_mismatch(self):
        """Test updating with mismatched lengths."""
        entries = [SRTEntry(1, "00:00:01,000", "00:00:04,000", "Hello")]
        translated = ["Hola", "Extra"]

        with pytest.raises(ValueError):
            update_texts(entries, translated)

    def test_update_texts_preserves_multiline(self):
        """Test updating texts preserves multiline structure."""
        entries = [
            SRTEntry(1, "00:00:01,000", "00:00:04,000", "Original\nmultiline"),
        ]
        translated = ["Translated\nmultiline"]
        updated = update_texts(entries, translated)

        assert updated[0].text == "Translated\nmultiline"
        assert "\n" in updated[0].text


class TestReconstructSrt:
    """Tests for reconstruct_srt function."""

    def test_reconstruct_srt(self):
        """Test reconstructing SRT format."""
        entries = [
            SRTEntry(1, "00:00:01,000", "00:00:04,000", "Hello"),
            SRTEntry(2, "00:00:05,000", "00:00:08,000", "World"),
        ]
        result = reconstruct_srt(entries)

        assert "Hello" in result
        assert "World" in result
        assert "00:00:01,000" in result

    def test_parse_and_reconstruct_preserves_timestamps(self):
        """Test that timestamps are preserved byte-for-byte through parse/reconstruct cycle."""
        original_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,234 --> 00:00:08,567
How are you?"""

        entries = parse_srt(original_content)
        reconstructed = reconstruct_srt(entries)

        # Timestamps should be preserved exactly
        assert "00:00:01,000 --> 00:00:04,000" in reconstructed
        assert "00:00:05,234 --> 00:00:08,567" in reconstructed
