"""create_patient_table

Revision ID: c75ee2f000a5
Revises: 290bbfb151b1
Create Date: 2022-11-17 15:49:59.853273

"""
from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import Table, MetaData

from passlib.hash import argon2
from datetime import datetime
import string
import random


# revision identifiers, used by Alembic.
revision = 'c75ee2f000a5'
down_revision = '290bbfb151b1'
branch_labels = None
depends_on = None


def upgrade():
    schema_upgrades()
    if context.get_x_argument(as_dictionary=True).get('data', None):
        data_upgrades()


def downgrade():
    if context.get_x_argument(as_dictionary=True).get('data', None):
        data_downgrades()
    schema_downgrades()


def schema_upgrades():
    op.create_table('patients',
        sa.Column('id', sa.String(length=20), nullable=False),
        sa.Column('forename', sa.String(), nullable=False),
        sa.Column('surname', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('modified_at', sa.DateTime()),
        sa.Column('modified_by', sa.Integer()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['modified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_patients_id'), 'patients', ['id'], unique=False)


def schema_downgrades():
    op.drop_index(op.f('ix_patients_id'), table_name='patients')
    op.drop_table('patients')


def data_upgrades():
    meta = MetaData(bind=op.get_bind())
    meta.reflect(only=('users', 'patients'))

    users_tbl = Table('users', meta)
    patients_tbl = Table('patients', meta)

    op.bulk_insert(users_tbl, [{
        'id': 1,
        'email': 'tester@gmail.com',
        'username': 'tester',
        'password': argon2.hash('Abcdef123')
    }])

    N = 200
    random.seed(1)
    patients = [
        {
            'id': ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            ),
            'forename': random.choice([
                'Jozef', 'Milan', 'Štefan',
                'Zuzana', 'Monika', 'Anna'
            ]),
            'surname': random.choice([
                'Kováč', 'Molnár', 'Lukáč',
                'Novák', 'Polák', 'Hudák'
            ]),
            'created_by': 1,
            'created_at': datetime.now().replace(microsecond=0)
        }
        for i in range(N)
    ]
    op.bulk_insert(patients_tbl, patients)


def data_downgrades():
    op.execute('delete from patients')
