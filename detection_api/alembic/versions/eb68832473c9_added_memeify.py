"""added memeify

Revision ID: eb68832473c9
Revises: 17a8f9d4c8a8
Create Date: 2025-04-25 17:37:37.633990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb68832473c9'
down_revision: Union[str, None] = '17a8f9d4c8a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the 'memeify' column with a default value of False for existing rows
    op.add_column('analysis_results', sa.Column('memeify', sa.Boolean(), nullable=False, server_default='false'))
    # Update existing rows to set 'memeify' to False
    op.execute("UPDATE analysis_results SET memeify = false")

    # Remove the server default to ensure future inserts explicitly set True or False
    op.alter_column('analysis_results', 'memeify', server_default=None)


def downgrade() -> None:
    # Drop the 'memeify' column
    op.drop_column('analysis_results', 'memeify')