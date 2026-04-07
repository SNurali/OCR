"""Add missing columns, image_hash, duplicate_count, and partial indexes

Revision ID: 001_production_hardening
Revises:
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "001_production_hardening"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check which columns already exist
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("passport_data")}

    # 1. Add missing columns from models.py
    new_columns = {
        "validation_status": sa.Column(
            "validation_status", sa.String(20), server_default="pending"
        ),
        "field_confidence": sa.Column("field_confidence", sa.Text()),
        "engine_used": sa.Column("engine_used", sa.String(20)),
        "document_type": sa.Column("document_type", sa.String(30)),
        "pipeline_stages": sa.Column("pipeline_stages", sa.Text()),
        "image_hash": sa.Column("image_hash", sa.String(64)),
        "duplicate_count": sa.Column(
            "duplicate_count", sa.Integer(), server_default="1"
        ),
    }

    for col_name, col_def in new_columns.items():
        if col_name not in existing_columns:
            op.add_column("passport_data", col_def)
            print(f"Added column: {col_name}")

    # 2. Add indexes
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("passport_data")}

    if "ix_passport_data_passport_number" not in existing_indexes:
        op.create_index(
            "ix_passport_data_passport_number",
            "passport_data",
            ["passport_number"],
            unique=False,
            postgresql_where=sa.text(
                "passport_number IS NOT NULL AND passport_number != ''"
            ),
        )
        print("Added index: ix_passport_data_passport_number")

    if "ix_passport_data_image_hash" not in existing_indexes:
        op.create_index(
            "ix_passport_data_image_hash",
            "passport_data",
            ["image_hash"],
            unique=False,
            postgresql_where=sa.text("image_hash IS NOT NULL"),
        )
        print("Added index: ix_passport_data_image_hash")

    if "ix_passport_data_recognition_status" not in existing_indexes:
        op.create_index(
            "ix_passport_data_recognition_status",
            "passport_data",
            ["mrz_valid", "passport_number", "birth_date"],
            unique=False,
        )
        print("Added index: ix_passport_data_recognition_status")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("passport_data")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("passport_data")}

    # Drop indexes
    for idx_name in [
        "ix_passport_data_passport_number",
        "ix_passport_data_image_hash",
        "ix_passport_data_recognition_status",
    ]:
        if idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="passport_data")

    # Drop columns
    for col_name in [
        "validation_status",
        "field_confidence",
        "engine_used",
        "document_type",
        "pipeline_stages",
        "image_hash",
        "duplicate_count",
    ]:
        if col_name in existing_columns:
            op.drop_column("passport_data", col_name)
