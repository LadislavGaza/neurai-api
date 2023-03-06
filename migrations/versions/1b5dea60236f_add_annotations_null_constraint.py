"""add_annotations_null_constraint

Revision ID: 1b5dea60236f
Revises: 748d5a65f67c
Create Date: 2023-03-04 18:38:12.837109

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1b5dea60236f"
down_revision = "748d5a65f67c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "annotations",
        "filename",
        existing_type=sa.VARCHAR(),
        nullable=True
    )
    op.alter_column(
        "annotations",
        "file_id",
        existing_type=sa.VARCHAR(),
        nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "annotations",
        "file_id",
        existing_type=sa.VARCHAR(),
        nullable=False
    )
    op.alter_column(
        "annotations",
        "filename",
        existing_type=sa.VARCHAR(),
        nullable=False
    )
