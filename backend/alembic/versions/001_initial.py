"""Initial schema — create all Ghost Negotiator tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Ghost Negotiator tables.

    Tables created (in dependency order):
    1. ``customers`` — CRM-lite customer records.
    2. ``conversations`` — individual chat turns with optional analysis.
    3. ``digital_twin_snapshots`` — point-in-time buyer personality profiles.
    4. ``simulation_results`` — per-strategy simulation outputs.
    """
    # --------------------------------------------------------------------- #
    # customers
    # --------------------------------------------------------------------- #
    op.create_table(
        "customers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "metadata_",
            postgresql.JSONB(asynchronous_creation=True),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # --------------------------------------------------------------------- #
    # conversations
    # --------------------------------------------------------------------- #
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(asynchronous_creation=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --------------------------------------------------------------------- #
    # digital_twin_snapshots
    # --------------------------------------------------------------------- #
    op.create_table(
        "digital_twin_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("price_sensitivity", sa.Float, nullable=False),
        sa.Column("urgency", sa.Float, nullable=False),
        sa.Column("risk_aversion", sa.Float, nullable=False),
        sa.Column("brand_loyalty", sa.Float, nullable=False),
        sa.Column("decision_speed", sa.Float, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --------------------------------------------------------------------- #
    # simulation_results
    # --------------------------------------------------------------------- #
    op.create_table(
        "simulation_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("offer_type", sa.String(100), nullable=False),
        sa.Column("discount_percent", sa.Float, nullable=False),
        sa.Column("bundle_value", sa.Float, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("close_probability", sa.Float, nullable=False),
        sa.Column("expected_profit", sa.Float, nullable=False),
        sa.Column("expected_value", sa.Float, nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("optimizer_reasoning", sa.Text, nullable=True),
        sa.Column(
            "winning_factors",
            postgresql.JSONB(asynchronous_creation=True),
            nullable=True,
        ),
        sa.Column("rollout_count", sa.Integer, nullable=True),
        sa.Column(
            "rollouts",
            postgresql.JSONB(asynchronous_creation=True),
            nullable=True,
        ),
        sa.Column("is_winner", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop all Ghost Negotiator tables in reverse dependency order."""
    op.drop_table("simulation_results")
    op.drop_table("digital_twin_snapshots")
    op.drop_table("conversations")
    op.drop_table("customers")
