"""anonymize_patients

Revision ID: b1ba681e573d
Revises: 1b5dea60236f
Create Date: 2023-03-09 21:34:29.931153

"""
from alembic import op
import sqlalchemy as sa


revision = "b1ba681e573d"
down_revision = "1b5dea60236f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("patients", "surname")
    op.drop_column("patients", "forename")


def downgrade() -> None:
    op.add_column(
        "patients", 
        sa.Column(
            "forename",
            sa.VARCHAR(), 
            autoincrement=False, 
            nullable=True))

    op.add_column(
        "patients", 
        sa.Column(
            "surname", 
            sa.VARCHAR(), 
            autoincrement=False, 
            nullable=True))
