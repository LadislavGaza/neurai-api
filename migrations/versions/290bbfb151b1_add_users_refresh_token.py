"""add_users_refresh_token

Revision ID: 290bbfb151b1
Revises: 0afdb03f9fea
Create Date: 2022-11-14 22:22:31.351599

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '290bbfb151b1'
down_revision = '0afdb03f9fea'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('refresh_token', sa.String(length=512), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'refresh_token')
    # ### end Alembic commands ###