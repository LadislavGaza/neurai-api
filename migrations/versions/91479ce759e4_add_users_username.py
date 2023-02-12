"""add_users_username

Revision ID: 91479ce759e4
Revises: b415f5dff43a
Create Date: 2023-02-08 21:59:04.562917

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91479ce759e4'
down_revision = 'b415f5dff43a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'username')
