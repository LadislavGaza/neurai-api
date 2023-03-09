"""add_annotations_unique_pair

Revision ID: 748d5a65f67c
Revises: 6d40004ab0be
Create Date: 2023-03-02 19:29:45.747752

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "748d5a65f67c"
down_revision = "6d40004ab0be"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "ix_annotation_name_mri_file_id",
        "annotations",
        ["name", "mri_file_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "ix_annotation_name_mri_file_id",
        "annotations",
        type_="unique"
    )
