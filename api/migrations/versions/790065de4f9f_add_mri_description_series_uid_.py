"""add_mri_description_series_uid_screenings
_study_uid

Revision ID: 790065de4f9f
Revises: 83c381fbeead
Create Date: 2023-04-21 18:40:23.406798

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '790065de4f9f'
down_revision = '83c381fbeead'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mri_files', sa.Column('description', sa.String(), nullable=True))
    op.add_column('mri_files', sa.Column('series_uid', sa.String(), nullable=True))
    op.add_column('screenings', sa.Column('study_uid', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('screenings', 'study_uid')
    op.drop_column('mri_files', 'series_uid')
    op.drop_column('mri_files', 'description')
