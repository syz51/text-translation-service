"""SRT subtitle entry model."""


class SRTEntry:
    """Represents a single subtitle entry."""

    def __init__(self, index: int, start_time: str, end_time: str, text: str):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.text = text

    def __repr__(self) -> str:
        return f"SRTEntry(index={self.index}, time={self.start_time} --> {self.end_time})"
