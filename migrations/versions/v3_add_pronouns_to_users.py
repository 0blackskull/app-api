"""Add pronouns column to users table

Revision ID: v3
Revises: v2
Create Date: 2025-09-05 00:00:00

Add pronouns column to store user's pronouns
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v3'
down_revision = 'v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pronouns column to users table
    op.add_column('users', sa.Column('pronouns', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove pronouns column from users table
    op.drop_column('users', 'pronouns')



