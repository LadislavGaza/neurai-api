"""add_annotations_mri_id

Revision ID: 6d40004ab0be
Revises: 014687fd4b27
Create Date: 2023-02-28 18:19:31.698687

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d40004ab0be'
down_revision = '782c2a745cd2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('annotations', sa.Column('mri_file_id', sa.Integer(), nullable=False))
    op.create_foreign_key(None, 'annotations', 'mri_files', ['mri_file_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint(None, 'annotations', type_='foreignkey')
    op.drop_column('annotations', 'mri_file_id')
