from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_epic22"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_items",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "lesson_plans",
        sa.Column("format", sa.String(length=64), nullable=False, server_default="lesson"),
    )
    op.create_index("ix_lesson_plans_format", "lesson_plans", ["format"])


def downgrade() -> None:
    op.drop_index("ix_lesson_plans_format", table_name="lesson_plans")
    op.drop_column("lesson_plans", "format")
    op.drop_column("learning_items", "metadata_json")
