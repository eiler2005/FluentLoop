from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_epic24"
down_revision = "0002_epic23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("evaluation_runs"):
        op.create_table(
            "evaluation_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("answer_text", sa.Text(), nullable=True),
            sa.Column("source_reference", sa.String(length=256), nullable=True),
            sa.Column("metrics_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "held_out_item_ids", sa.JSON(), nullable=False, server_default="[]"
            ),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(op.get_bind())
    _create_index_if_missing(
        inspector, "evaluation_runs", "ix_evaluation_runs_user_id", ["user_id"]
    )
    _create_index_if_missing(
        inspector, "evaluation_runs", "ix_evaluation_runs_kind", ["kind"]
    )
    _create_index_if_missing(
        inspector,
        "evaluation_runs",
        "ix_evaluation_runs_period_start",
        ["period_start"],
    )
    _create_index_if_missing(
        inspector, "evaluation_runs", "ix_evaluation_runs_period_end", ["period_end"]
    )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("learning_metric_snapshots"):
        op.create_table(
            "learning_metric_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("metrics_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("summary_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(op.get_bind())
    _create_index_if_missing(
        inspector,
        "learning_metric_snapshots",
        "ix_learning_metric_snapshots_user_id",
        ["user_id"],
    )
    _create_index_if_missing(
        inspector,
        "learning_metric_snapshots",
        "ix_learning_metric_snapshots_period_start",
        ["period_start"],
    )
    _create_index_if_missing(
        inspector,
        "learning_metric_snapshots",
        "ix_learning_metric_snapshots_period_end",
        ["period_end"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("learning_metric_snapshots"):
        for index_name in _index_names(inspector, "learning_metric_snapshots"):
            if index_name.startswith("ix_learning_metric_snapshots_"):
                op.drop_index(index_name, table_name="learning_metric_snapshots")
        op.drop_table("learning_metric_snapshots")

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("evaluation_runs"):
        for index_name in _index_names(inspector, "evaluation_runs"):
            if index_name.startswith("ix_evaluation_runs_"):
                op.drop_index(index_name, table_name="evaluation_runs")
        op.drop_table("evaluation_runs")


def _create_index_if_missing(
    inspector: sa.Inspector, table_name: str, index_name: str, columns: list[str]
) -> None:
    if index_name not in _index_names(inspector, table_name):
        op.create_index(index_name, table_name, columns)


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}
