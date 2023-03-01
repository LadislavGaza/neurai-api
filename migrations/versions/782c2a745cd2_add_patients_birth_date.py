"""add_patients_birth_date

Revision ID: 782c2a745cd2
Revises: 014687fd4b27
Create Date: 2023-02-22 23:53:58.515801

"""
from alembic import op, context
import sqlalchemy as sa

from sqlalchemy import Table, MetaData
from datetime import datetime, date
import string
import random


# revision identifiers, used by Alembic.
revision = '782c2a745cd2'
down_revision = '014687fd4b27'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_upgrades()
    if context.get_x_argument(as_dictionary=True).get("data", None):
        data_upgrades()


def downgrade() -> None:
    if context.get_x_argument(as_dictionary=True).get('data', None):
        data_downgrades()
    schema_downgrades()


def schema_upgrades():
    op.add_column('patients', sa.Column('birth_date', sa.Date(), nullable=False))


def schema_downgrades():
    op.drop_column('patients', 'birth_date')


def data_upgrades():
    meta = MetaData()
    meta.reflect(
        bind=op.get_bind(),
        only=("users", "patients")
    )

    users_tbl = Table("users", meta)
    patients_tbl = Table("patients", meta)

    N = 200
    random.seed(1)
    patients = [
        {
            "id": "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            ),
            "forename": random.choice([
                "Jozef", "Milan", "Štefan",
                "Zuzana", "Monika", "Anna"
            ]),
            "surname": random.choice([
                "Kováč", "Molnár", "Lukáč",
                "Novák", "Polák", "Hudák"
            ]),
            "birth_date": date.today(),
            "created_by": 1,
            "created_at": datetime.now().replace(microsecond=0)
        }
        for i in range(N)
    ]
    op.bulk_insert(patients_tbl, patients)


def data_downgrades():
    op.execute("delete from patients")
