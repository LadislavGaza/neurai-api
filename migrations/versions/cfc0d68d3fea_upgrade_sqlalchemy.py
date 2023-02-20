"""upgrade sqlalchemy

Revision ID: cfc0d68d3fea
Revises: 042df21ffbec
Create Date: 2023-02-20 12:12:11.004005

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfc0d68d3fea'
down_revision = '042df21ffbec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_mri_files_id', table_name='mri_files')
    op.drop_constraint('mri_files_created_by_fkey', 'mri_files', type_='foreignkey')
    op.drop_constraint('mri_files_modified_by_fkey', 'mri_files', type_='foreignkey')
    op.create_foreign_key(None, 'mri_files', 'users', ['modified_by'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'mri_files', 'users', ['created_by'], ['id'], ondelete='CASCADE')
    op.drop_index('ix_patients_id', table_name='patients')
    op.drop_index('ix_users_id', table_name='users')


def downgrade() -> None:
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_patients_id', 'patients', ['id'], unique=False)
    op.drop_constraint(None, 'mri_files', type_='foreignkey')
    op.drop_constraint(None, 'mri_files', type_='foreignkey')
    op.create_foreign_key('mri_files_modified_by_fkey', 'mri_files', 'users', ['modified_by'], ['id'])
    op.create_foreign_key('mri_files_created_by_fkey', 'mri_files', 'users', ['created_by'], ['id'])
    op.create_index('ix_mri_files_id', 'mri_files', ['id'], unique=False)
