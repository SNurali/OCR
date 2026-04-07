"""add_analytics_fields_to_passport_data

Revision ID: e2928dfddab7
Revises: 003_billing
Create Date: 2026-04-04 23:45:49.496092

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2928dfddab7"
down_revision = "003_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "passport_data",
        sa.Column("citizenship", sa.String(50), nullable=True, server_default="UZ"),
    )
    op.add_column("passport_data", sa.Column("age_group", sa.String(20), nullable=True))
    op.add_column(
        "passport_data",
        sa.Column(
            "is_foreigner", sa.Boolean(), nullable=True, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "passport_data",
        sa.Column(
            "ocr_confidence_avg",
            sa.Float(),
            nullable=True,
            server_default=sa.text("0.0"),
        ),
    )
    op.add_column(
        "passport_data",
        sa.Column(
            "mrz_confidence", sa.Float(), nullable=True, server_default=sa.text("0.0")
        ),
    )
    op.add_column(
        "passport_data",
        sa.Column("field_errors", sa.JSON(), nullable=True, server_default="{}"),
    )


def downgrade():
    op.drop_column("passport_data", "field_errors")
    op.drop_column("passport_data", "mrz_confidence")
    op.drop_column("passport_data", "ocr_confidence_avg")
    op.drop_column("passport_data", "is_foreigner")
    op.drop_column("passport_data", "age_group")
    op.drop_column("passport_data", "citizenship")
