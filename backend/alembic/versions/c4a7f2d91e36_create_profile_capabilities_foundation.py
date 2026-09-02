"""create profile capabilities foundation

Revision ID: c4a7f2d91e36
Revises: b6a7d4e9c231
Create Date: 2026-09-02 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.profile_capabilities import (
    postgres_whitespace_literal,
    sqlite_whitespace_literal,
)

# revision identifiers, used by Alembic.
revision: str = "c4a7f2d91e36"
down_revision: str | Sequence[str] | None = "b6a7d4e9c231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _confirmer_whitespace_literal() -> str:
    """Dialect-aware SQL literal for the confirmer whitespace character set.

    PostgreSQL uses the U&-escape form (no physical control/newline chars).
    All other dialects (including SQLite) use the physical-character form.
    """
    dialect_name = op.get_context().dialect.name
    if dialect_name == "postgresql":
        return postgres_whitespace_literal()
    return sqlite_whitespace_literal()


def upgrade() -> None:
    """Create the three foundation tables and backfill section rows."""
    op.create_table(
        "pnc_profile_technology_capability",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("technology_code", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "state IN ('SUPPORTED', 'UNSUPPORTED', 'UNKNOWN')",
            name="ck_pnc_profile_technology_capability_state",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["pnc_enterprise_profile.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technology_code"],
            ["pnc_technology_type.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "technology_code",
            name="uq_pnc_profile_technology_capability_identity",
        ),
    )
    op.create_index(
        "ix_pnc_profile_technology_capability_technology_code",
        "pnc_profile_technology_capability",
        ["technology_code"],
    )

    op.create_table(
        "pnc_profile_material_capability",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("material_group_code", sa.String(length=50), nullable=True),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "((material_group_code IS NOT NULL AND material_id IS NULL) OR "
            "(material_group_code IS NULL AND material_id IS NOT NULL))",
            name="ck_pnc_profile_material_capability_exactly_one_target",
        ),
        sa.CheckConstraint(
            "state IN ('SUPPORTED', 'UNSUPPORTED', 'UNKNOWN')",
            name="ck_pnc_profile_material_capability_state",
        ),
        sa.ForeignKeyConstraint(
            ["material_group_code"],
            ["pnc_material_group.code"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["pnc_material.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["pnc_enterprise_profile.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "material_group_code",
            name="uq_pnc_profile_material_capability_group_identity",
        ),
        sa.UniqueConstraint(
            "profile_id",
            "material_id",
            name="uq_pnc_profile_material_capability_material_identity",
        ),
    )
    op.create_index(
        "ix_pnc_profile_material_capability_group_code",
        "pnc_profile_material_capability",
        ["material_group_code"],
    )
    op.create_index(
        "ix_pnc_profile_material_capability_material_id",
        "pnc_profile_material_capability",
        ["material_id"],
    )

    ws = _confirmer_whitespace_literal()

    op.create_table(
        "pnc_profile_section_completeness",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("section_code", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "section_code IN ('TECHNOLOGIES', 'MATERIALS')",
            name="ck_pnc_profile_section_completeness_section_code",
        ),
        sa.CheckConstraint(
            "state IN ('CONFIRMED_COMPLETE', 'PARTIAL', 'UNKNOWN')",
            name="ck_pnc_profile_section_completeness_state",
        ),
        sa.CheckConstraint(
            "((state = 'CONFIRMED_COMPLETE' "
            "AND confirmed_at IS NOT NULL "
            "AND confirmed_by IS NOT NULL "
            "AND length(trim(confirmed_by, "
            f"{ws})) "
            "BETWEEN 1 AND 128) "
            "OR (state IN ('PARTIAL', 'UNKNOWN') "
            "AND confirmed_at IS NULL "
            "AND confirmed_by IS NULL))",
            name="ck_pnc_profile_section_completeness_confirmation",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["pnc_enterprise_profile.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("profile_id", "section_code"),
    )

    op.execute(
        sa.text(
            "INSERT INTO pnc_profile_section_completeness "
            "(profile_id, section_code, state, confirmed_at, confirmed_by) "
            "SELECT id, 'TECHNOLOGIES', 'UNKNOWN', NULL, NULL "
            "FROM pnc_enterprise_profile"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO pnc_profile_section_completeness "
            "(profile_id, section_code, state, confirmed_at, confirmed_by) "
            "SELECT id, 'MATERIALS', 'UNKNOWN', NULL, NULL "
            "FROM pnc_enterprise_profile"
        )
    )


def downgrade() -> None:
    """Remove the profile capabilities foundation."""
    op.drop_table("pnc_profile_section_completeness")
    op.drop_index(
        "ix_pnc_profile_material_capability_material_id",
        table_name="pnc_profile_material_capability",
    )
    op.drop_index(
        "ix_pnc_profile_material_capability_group_code",
        table_name="pnc_profile_material_capability",
    )
    op.drop_table("pnc_profile_material_capability")
    op.drop_index(
        "ix_pnc_profile_technology_capability_technology_code",
        table_name="pnc_profile_technology_capability",
    )
    op.drop_table("pnc_profile_technology_capability")
