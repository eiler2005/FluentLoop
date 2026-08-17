"""EPIC-25: daily vocabulary loop.

Adds the per-user preference blob, the user-added priority flag, and the
delivery log that makes the minute tick idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_epic25"
down_revision = "0003_epic24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "preferences_json" not in _column_names(inspector, "users"):
        op.add_column(
            "users",
            sa.Column("preferences_json", sa.JSON(), nullable=False, server_default="{}"),
        )

    inspector = sa.inspect(op.get_bind())
    if "priority" not in _column_names(inspector, "learning_items"):
        op.add_column(
            "learning_items",
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        )

    inspector = sa.inspect(op.get_bind())
    _create_index_if_missing(
        inspector, "learning_items", "ix_learning_items_priority", ["priority"]
    )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("vocab_deliveries"):
        op.create_table(
            "vocab_deliveries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("local_date", sa.Date(), nullable=False),
            sa.Column("slot", sa.String(length=16), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="claimed"
            ),
            sa.Column("poll_id", sa.BigInteger(), nullable=True),
            sa.Column("message_id", sa.Integer(), nullable=True),
            sa.Column(
                "learning_item_ids", sa.JSON(), nullable=False, server_default="[]"
            ),
            sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "local_date", "slot", "seq", name="uq_vocab_delivery_slot"
            ),
        )

    inspector = sa.inspect(op.get_bind())
    for index_name, columns in (
        ("ix_vocab_deliveries_user_id", ["user_id"]),
        ("ix_vocab_deliveries_local_date", ["local_date"]),
        ("ix_vocab_deliveries_slot", ["slot"]),
        ("ix_vocab_deliveries_poll_id", ["poll_id"]),
    ):
        _create_index_if_missing(inspector, "vocab_deliveries", index_name, columns)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("vocab_deliveries"):
        for index_name in _index_names(inspector, "vocab_deliveries"):
            if index_name.startswith("ix_vocab_deliveries_"):
                op.drop_index(index_name, table_name="vocab_deliveries")
        op.drop_table("vocab_deliveries")

    inspector = sa.inspect(op.get_bind())
    if "priority" in _column_names(inspector, "learning_items"):
        if "ix_learning_items_priority" in _index_names(inspector, "learning_items"):
            op.drop_index("ix_learning_items_priority", table_name="learning_items")
        with op.batch_alter_table("learning_items") as batch_op:
            batch_op.drop_column("priority")

    inspector = sa.inspect(op.get_bind())
    if "preferences_json" in _column_names(inspector, "users"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("preferences_json")


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_index_if_missing(
    inspector: sa.Inspector, table_name: str, index_name: str, columns: list[str]
) -> None:
    if index_name not in _index_names(inspector, table_name):
        op.create_index(index_name, table_name, columns)


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}
