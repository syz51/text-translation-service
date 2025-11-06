"""Database models."""

from datetime import datetime, timezone
import enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobStatus(str, enum.Enum):
    """Transcription job status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class TranscriptionJob(Base):
    """Transcription job model."""

    __tablename__ = "transcription_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.QUEUED.value)
    audio_s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    srt_s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_detection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    speaker_labels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assemblyai_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    def __repr__(self) -> str:
        """String representation of TranscriptionJob."""
        return f"<TranscriptionJob(id={self.id}, status={self.status})>"
