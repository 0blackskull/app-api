"""Add trust_analysis column to users table

Revision ID: v2
Revises: v1
Create Date: 2024-12-19 10:00:00

Add trust_analysis column to store user's trust and behavior analysis
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v2'
down_revision = 'v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add trust_analysis column to users table
    op.add_column('users', sa.Column('trust_analysis', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove trust_analysis column from users table
    op.drop_column('users', 'trust_analysis')
