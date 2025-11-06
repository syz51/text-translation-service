"""add_index_on_status_column

Revision ID: 7bbe0b7dc3dc
Revises: f28765532785
Create Date: 2025-11-06 07:32:22.825857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bbe0b7dc3dc'
down_revision: Union[str, Sequence[str], None] = 'f28765532785'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index on transcription_jobs.status column for performance."""
    op.create_index(
        'ix_transcription_jobs_status',
        'transcription_jobs',
        ['status'],
        unique=False
    )


def downgrade() -> None:
    """Remove index on transcription_jobs.status column."""
    op.drop_index('ix_transcription_jobs_status', table_name='transcription_jobs')
