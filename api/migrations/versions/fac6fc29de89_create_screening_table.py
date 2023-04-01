"""create_screening_table

Revision ID: fac6fc29de89
Revises: b1ba681e573d
Create Date: 2023-03-21 19:14:30.556217

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fac6fc29de89'
down_revision = 'b1ba681e573d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('TRUNCATE TABLE mri_files CASCADE')

    op.create_table('screenings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('patient_id', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.Column('modified_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['modified_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('mri_files', sa.Column('screening_id', sa.Integer(), nullable=False))
    op.create_foreign_key('mri_files_screening_id_fk', 'mri_files', 'screenings', ['screening_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('ix_screening_name_patient_id', 'screenings', ['name', 'patient_id'])
    op.create_unique_constraint('ix_mri_files_filename_screening_id', 'mri_files', ['filename', 'screening_id'])


def downgrade() -> None:
    op.drop_constraint('ix_screening_name_patient_id', 'screenings', type_='unique')
    op.drop_constraint('ix_mri_files_filename_screening_id', 'mri_files', type_='unique')
    op.drop_constraint('mri_files_screening_id_fk', 'mri_files', type_='foreignkey')
    op.drop_column('mri_files', 'screening_id')
    op.drop_table('screenings')
