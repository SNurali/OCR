"""add api_keys table

Revision ID: 002_api_keys
Revises: 001_production_hardening
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "002_api_keys"
down_revision = "001_production_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("key_hash", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("key_prefix", sa.String(8), index=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "owner_id", sa.Integer(), sa.ForeignKey("dashboard_users.id"), index=True
        ),
        sa.Column("rate_limit_per_minute", sa.Integer(), default=60),
        sa.Column("rate_limit_per_day", sa.Integer(), default=10000),
        sa.Column("daily_usage", sa.Integer(), default=0),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("api_keys")
