"""add_uploaded_by_and_field_confidence

Revision ID: 3b3fdec1f1f4
Revises: e2928dfddab7
Create Date: 2026-04-05 00:16:58.714156

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "3b3fdec1f1f4"
down_revision = "e2928dfddab7"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col["name"] for col in inspector.get_columns("passport_data")]

    if "uploaded_by" not in columns:
        op.add_column(
            "passport_data",
            sa.Column(
                "uploaded_by",
                sa.Integer(),
                sa.ForeignKey("dashboard_users.id"),
                nullable=True,
            ),
        )
    if "field_confidence" not in columns:
        op.add_column(
            "passport_data",
            sa.Column(
                "field_confidence", sa.JSON(), nullable=True, server_default="{}"
            ),
        )
    if "recognition_status" not in columns:
        op.add_column(
            "passport_data",
            sa.Column(
                "recognition_status",
                sa.String(20),
                nullable=True,
                server_default="partial",
            ),
        )

    indexes = [idx["name"] for idx in inspector.get_indexes("passport_data")]
    if "ix_passport_data_uploaded_by" not in indexes:
        op.create_index(
            "ix_passport_data_uploaded_by", "passport_data", ["uploaded_by"]
        )


def downgrade():
    op.drop_index("ix_passport_data_uploaded_by", "passport_data")
    op.drop_column("passport_data", "recognition_status")
    op.drop_column("passport_data", "field_confidence")
    op.drop_column("passport_data", "uploaded_by")
