"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "certificate_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_name", sa.String(length=200), nullable=False),
        sa.Column("background_image_path", sa.String(length=500), nullable=False),
        sa.Column("field_positions_json", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_certificate_templates_id"), "certificate_templates", ["id"], unique=False)

    op.create_table(
        "application_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_name", sa.String(length=300), nullable=False),
        sa.Column("certificate_prefix", sa.String(length=50), nullable=False),
        sa.Column("automatic_numbering", sa.Boolean(), nullable=False),
        sa.Column("current_year", sa.Integer(), nullable=False),
        sa.Column("current_serial_number", sa.Integer(), nullable=False),
        sa.Column("number_padding", sa.Integer(), nullable=False),
        sa.Column("default_logo_path", sa.String(length=500), nullable=True),
        sa.Column("default_signature_path", sa.String(length=500), nullable=True),
        sa.Column("default_template_id", sa.Integer(), nullable=True),
        sa.Column("date_format", sa.String(length=50), nullable=False),
        sa.Column("default_address", sa.String(length=500), nullable=True),
        sa.Column("pdf_storage_directory", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["default_template_id"], ["certificate_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_settings_id"), "application_settings", ["id"], unique=False)

    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certificate_number", sa.String(length=100), nullable=False),
        sa.Column("candidate_name", sa.String(length=300), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("training_date", sa.Date(), nullable=False),
        sa.Column("driving_licence_number", sa.String(length=100), nullable=True),
        sa.Column("certificate_type", sa.String(length=100), nullable=True),
        sa.Column("company_name", sa.String(length=300), nullable=True),
        sa.Column("training_centre_name", sa.String(length=300), nullable=True),
        sa.Column("authorized_person_name", sa.String(length=200), nullable=True),
        sa.Column("certificate_title", sa.String(length=300), nullable=True),
        sa.Column("certificate_description", sa.Text(), nullable=True),
        sa.Column("logo_path", sa.String(length=500), nullable=True),
        sa.Column("signature_path", sa.String(length=500), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("print_status", sa.String(length=50), nullable=False),
        sa.Column("print_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["certificate_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_certificates_certificate_number"), "certificates", ["certificate_number"], unique=True)
    op.create_index(op.f("ix_certificates_id"), "certificates", ["id"], unique=False)

    op.create_table(
        "print_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certificate_id", sa.Integer(), nullable=False),
        sa.Column("printed_by", sa.Integer(), nullable=True),
        sa.Column("printed_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["certificate_id"], ["certificates.id"]),
        sa.ForeignKeyConstraint(["printed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_print_history_id"), "print_history", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_print_history_id"), table_name="print_history")
    op.drop_table("print_history")
    op.drop_index(op.f("ix_certificates_id"), table_name="certificates")
    op.drop_index(op.f("ix_certificates_certificate_number"), table_name="certificates")
    op.drop_table("certificates")
    op.drop_index(op.f("ix_application_settings_id"), table_name="application_settings")
    op.drop_table("application_settings")
    op.drop_index(op.f("ix_certificate_templates_id"), table_name="certificate_templates")
    op.drop_table("certificate_templates")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
