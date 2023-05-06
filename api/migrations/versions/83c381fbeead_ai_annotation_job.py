"""ai_annotation_job

Revision ID: 83c381fbeead
Revises: fac6fc29de89
Create Date: 2023-04-17 01:05:55.586211

"""
from alembic import op
import sqlalchemy as sa


revision = '83c381fbeead'
down_revision = 'fac6fc29de89'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('annotations', sa.Column('is_ai', sa.Boolean(), nullable=False, server_default="false"))
    op.add_column('annotations', sa.Column('visible', sa.Boolean(), nullable=False, server_default="false"))
    op.add_column('annotations', sa.Column('job_name', sa.String(), nullable=True))


def downgrade():
    op.drop_column('annotations', 'job_name')
    op.drop_column('annotations', 'visible')
    op.drop_column('annotations', 'is_ai')
