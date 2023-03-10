"""create_patients_table

Revision ID: 8ce216dbf609
Revises: 
Create Date: 2023-03-10 00:22:40.431830

"""
from alembic import op, context
import sqlalchemy as sa

from sqlalchemy import Table, MetaData
import string
import random


# revision identifiers, used by Alembic.
revision = "8ce216dbf609"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema_upgrades()
    if context.get_x_argument(as_dictionary=True).get("data", None):
        data_upgrades()


def downgrade():
    if context.get_x_argument(as_dictionary=True).get("data", None):
        data_downgrades()
    schema_downgrades()


def schema_upgrades() -> None:
    op.create_table("patients",
        sa.Column("id", sa.String(length=20), nullable=False),
        sa.Column("forename", sa.String(), nullable=False),
        sa.Column("surname", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )


def schema_downgrades() -> None:
    op.drop_table("patients")


def data_upgrades():
    meta = MetaData()
    meta.reflect(
        bind=op.get_bind(),
        only=("patients",)
    )
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
            ])
        }
        for i in range(N)
    ]
    op.bulk_insert(patients_tbl, patients)


def data_downgrades():
    op.execute("delete from patients")
