"""Add genz_style_enabled to users

Revision ID: v4
Revises: v3
Create Date: 2025-09-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v4'
down_revision = 'v3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('genz_style_enabled', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('users', 'genz_style_enabled')


