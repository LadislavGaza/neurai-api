"""authorized_email

Revision ID: 042df21ffbec
Revises: b415f5dff43a
Create Date: 2023-02-17 00:34:33.832204

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '042df21ffbec'
down_revision = 'b415f5dff43a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('patients_created_by_fkey', 'patients', type_='foreignkey')
    op.drop_constraint('patients_modified_by_fkey', 'patients', type_='foreignkey')
    op.create_foreign_key(None, 'patients', 'users', ['created_by'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'patients', 'users', ['modified_by'], ['id'], ondelete='CASCADE')
    op.add_column('users', sa.Column('authorized_email', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'authorized_email')
    op.drop_constraint(None, 'patients', type_='foreignkey')
    op.drop_constraint(None, 'patients', type_='foreignkey')
    op.create_foreign_key('patients_modified_by_fkey', 'patients', 'users', ['modified_by'], ['id'])
    op.create_foreign_key('patients_created_by_fkey', 'patients', 'users', ['created_by'], ['id'])
