"""create_mri_files_table

Revision ID: 5ea91623c6da
Revises: c75ee2f000a5
Create Date: 2022-11-17 22:07:37.871007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ea91623c6da'
down_revision = 'c75ee2f000a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('mri_files',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('patient_id', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.Column('modified_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['modified_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mri_files_id'), 'mri_files', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mri_files_id'), table_name='mri_files')
    op.drop_table('mri_files')
