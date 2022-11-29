"""add file_id to mri_files

Revision ID: b415f5dff43a
Revises: 5ea91623c6da
Create Date: 2022-11-29 23:08:38.697691

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b415f5dff43a'
down_revision = '5ea91623c6da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mri_files', sa.Column('file_id', sa.String(), nullable=False))


def downgrade() -> None:
    op.drop_column('mri_files', 'file_id')
