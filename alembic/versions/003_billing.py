"""add billing tables: subscription_plans, usage_records

Revision ID: 003_billing
Revises: 002_api_keys
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "003_billing"
down_revision = "002_api_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("price_cents", sa.Integer(), default=0),
        sa.Column("documents_per_month", sa.Integer(), default=1000),
        sa.Column("rate_limit_per_minute", sa.Integer(), default=60),
        sa.Column("rate_limit_per_day", sa.Integer(), default=10000),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "api_key_id",
            sa.Integer(),
            sa.ForeignKey("api_keys.id"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "document_id", sa.Integer(), sa.ForeignKey("passport_data.id"), index=True
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), default=0),
        sa.Column("confidence", sa.Float(), default=0.0),
        sa.Column("engine_used", sa.String(30)),
        sa.Column("cost_cents", sa.Integer(), default=0),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Index("idx_usage_api_key_date", "api_key_id", "created_at"),
    )


def downgrade():
    op.drop_table("usage_records")
    op.drop_table("subscription_plans")
