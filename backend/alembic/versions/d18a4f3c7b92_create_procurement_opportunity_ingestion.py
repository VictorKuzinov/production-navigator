"""create procurement opportunity ingestion

Revision ID: d18a4f3c7b92
Revises: c4a7f2d91e36
Create Date: 2026-09-02 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d18a4f3c7b92"
down_revision: str | Sequence[str] | None = "c4a7f2d91e36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pnc_procurement_opportunity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("procurement_number", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("customer", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("procurement_type", sa.String(length=50), nullable=True),
        sa.Column("okpd2_codes", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("product_type_codes_state", sa.String(length=7), nullable=False),
        sa.Column(
            "material_requirements_state",
            sa.String(length=7),
            nullable=False,
        ),
        sa.Column(
            "technology_requirements_state",
            sa.String(length=7),
            nullable=False,
        ),
        sa.Column(
            "equipment_requirements_state",
            sa.String(length=7),
            nullable=False,
        ),
        sa.Column(
            "required_certificates_state",
            sa.String(length=7),
            nullable=False,
        ),
        sa.Column(
            "dimensional_mass_requirements",
            sa.JSON(none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "quality_requirements",
            sa.JSON(none_as_null=True),
            nullable=True,
        ),
        sa.Column("price_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("price_currency", sa.String(length=3), nullable=True),
        sa.Column("region_code", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("application_deadline_date", sa.Date(), nullable=True),
        sa.Column(
            "application_deadline_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("execution_deadline_date", sa.Date(), nullable=True),
        sa.Column(
            "execution_deadline_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "source = trim(source) AND source = lower(source) "
            "AND length(source) > 0",
            name="ck_pnc_procurement_opportunity_source_nonblank_lower",
        ),
        sa.CheckConstraint(
            "external_id = trim(external_id) AND length(external_id) > 0",
            name="ck_pnc_procurement_opportunity_external_id_nonblank_trimmed",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_pnc_procurement_opportunity_title_nonblank",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'CANCELLED', 'AWARDED', 'UNKNOWN')",
            name="ck_pnc_procurement_opportunity_status",
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_currency IS NOT NULL",
            name="ck_pnc_procurement_opportunity_price_currency_required",
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0",
            name="ck_pnc_procurement_opportunity_price_nonnegative",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR unit IS NOT NULL",
            name="ck_pnc_procurement_opportunity_quantity_unit_required",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_pnc_procurement_opportunity_quantity_positive",
        ),
        sa.CheckConstraint(
            "NOT (application_deadline_date IS NOT NULL "
            "AND application_deadline_at IS NOT NULL)",
            name="ck_pnc_procurement_opportunity_application_deadline_shape",
        ),
        sa.CheckConstraint(
            "NOT (execution_deadline_date IS NOT NULL "
            "AND execution_deadline_at IS NOT NULL)",
            name="ck_pnc_procurement_opportunity_execution_deadline_shape",
        ),
        sa.CheckConstraint(
            "product_type_codes_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_product_types_state",
        ),
        sa.CheckConstraint(
            "material_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_materials_state",
        ),
        sa.CheckConstraint(
            "technology_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_technologies_state",
        ),
        sa.CheckConstraint(
            "equipment_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_equipment_state",
        ),
        sa.CheckConstraint(
            "required_certificates_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_certificates_state",
        ),
        sa.ForeignKeyConstraint(
            ["region_code"],
            ["pnc_region.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_pnc_procurement_opportunity_identity",
        ),
    )
    op.create_index(
        "ix_pnc_procurement_opportunity_region_code",
        "pnc_procurement_opportunity",
        ["region_code"],
    )

    op.create_table(
        "pnc_procurement_opportunity_product_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("product_type_code", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["pnc_procurement_opportunity.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_type_code"],
            ["pnc_product_type.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "product_type_code",
            name="uq_pnc_procurement_opportunity_product_type_target",
        ),
    )
    op.create_index(
        "ix_pnc_procurement_opportunity_product_type_code",
        "pnc_procurement_opportunity_product_type",
        ["product_type_code"],
    )

    op.create_table(
        "pnc_procurement_material_requirement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("material_group_code", sa.String(length=50), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("requirement_strength", sa.String(length=12), nullable=False),
        sa.CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_material_requirement_strength",
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
            ["opportunity_id"],
            ["pnc_procurement_opportunity.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_pnc_procurement_material_requirement_group_target",
        "pnc_procurement_material_requirement",
        ["opportunity_id", "material_group_code"],
        unique=True,
        postgresql_where=sa.text("material_id IS NULL"),
        sqlite_where=sa.text("material_id IS NULL"),
    )
    op.create_index(
        "uq_pnc_procurement_material_requirement_material_target",
        "pnc_procurement_material_requirement",
        ["opportunity_id", "material_id"],
        unique=True,
        postgresql_where=sa.text("material_id IS NOT NULL"),
        sqlite_where=sa.text("material_id IS NOT NULL"),
    )
    op.create_index(
        "ix_pnc_procurement_material_requirement_group_code",
        "pnc_procurement_material_requirement",
        ["material_group_code"],
    )
    op.create_index(
        "ix_pnc_procurement_material_requirement_material_id",
        "pnc_procurement_material_requirement",
        ["material_id"],
    )

    op.create_table(
        "pnc_procurement_technology_requirement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("technology_code", sa.String(length=50), nullable=False),
        sa.Column("requirement_strength", sa.String(length=12), nullable=False),
        sa.CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_technology_requirement_strength",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["pnc_procurement_opportunity.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technology_code"],
            ["pnc_technology_type.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "technology_code",
            name="uq_pnc_procurement_technology_requirement_target",
        ),
    )
    op.create_index(
        "ix_pnc_procurement_technology_requirement_technology_code",
        "pnc_procurement_technology_requirement",
        ["technology_code"],
    )

    op.create_table(
        "pnc_procurement_equipment_requirement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("equipment_type_code", sa.String(length=50), nullable=False),
        sa.Column("cnc", sa.Boolean(), nullable=True),
        sa.Column("axes", sa.Integer(), nullable=True),
        sa.Column("working_zone_x_mm", sa.Numeric(18, 3), nullable=True),
        sa.Column("working_zone_y_mm", sa.Numeric(18, 3), nullable=True),
        sa.Column("working_zone_z_mm", sa.Numeric(18, 3), nullable=True),
        sa.Column("diameter_mm", sa.Numeric(18, 3), nullable=True),
        sa.Column("requirement_strength", sa.String(length=12), nullable=False),
        sa.CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_equipment_requirement_strength",
        ),
        sa.CheckConstraint(
            "axes IS NULL OR axes >= 1",
            name="ck_pnc_procurement_equipment_requirement_axes",
        ),
        sa.CheckConstraint(
            "working_zone_x_mm IS NULL OR working_zone_x_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_x_positive",
        ),
        sa.CheckConstraint(
            "working_zone_y_mm IS NULL OR working_zone_y_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_y_positive",
        ),
        sa.CheckConstraint(
            "working_zone_z_mm IS NULL OR working_zone_z_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_z_positive",
        ),
        sa.CheckConstraint(
            "diameter_mm IS NULL OR diameter_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_diameter_positive",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_type_code"],
            ["pnc_equipment_type.code"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["pnc_procurement_opportunity.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "equipment_type_code",
            name="uq_pnc_procurement_equipment_requirement_target",
        ),
    )
    op.create_index(
        "ix_pnc_procurement_equipment_requirement_equipment_type_code",
        "pnc_procurement_equipment_requirement",
        ["equipment_type_code"],
    )

    op.create_table(
        "pnc_procurement_certificate_requirement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("certificate_type_code", sa.String(length=50), nullable=False),
        sa.Column("requirement_strength", sa.String(length=12), nullable=False),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_certificate_requirement_strength",
        ),
        sa.ForeignKeyConstraint(
            ["certificate_type_code"],
            ["pnc_certificate_type.code"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["pnc_procurement_opportunity.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "certificate_type_code",
            name="uq_pnc_procurement_certificate_requirement_target",
        ),
    )
    op.create_index(
        "ix_pnc_procurement_certificate_requirement_type_code",
        "pnc_procurement_certificate_requirement",
        ["certificate_type_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pnc_procurement_certificate_requirement_type_code",
        table_name="pnc_procurement_certificate_requirement",
    )
    op.drop_table("pnc_procurement_certificate_requirement")
    op.drop_index(
        "ix_pnc_procurement_equipment_requirement_equipment_type_code",
        table_name="pnc_procurement_equipment_requirement",
    )
    op.drop_table("pnc_procurement_equipment_requirement")
    op.drop_index(
        "ix_pnc_procurement_technology_requirement_technology_code",
        table_name="pnc_procurement_technology_requirement",
    )
    op.drop_table("pnc_procurement_technology_requirement")
    op.drop_index(
        "ix_pnc_procurement_material_requirement_material_id",
        table_name="pnc_procurement_material_requirement",
    )
    op.drop_index(
        "ix_pnc_procurement_material_requirement_group_code",
        table_name="pnc_procurement_material_requirement",
    )
    op.drop_index(
        "uq_pnc_procurement_material_requirement_material_target",
        table_name="pnc_procurement_material_requirement",
    )
    op.drop_index(
        "uq_pnc_procurement_material_requirement_group_target",
        table_name="pnc_procurement_material_requirement",
    )
    op.drop_table("pnc_procurement_material_requirement")
    op.drop_index(
        "ix_pnc_procurement_opportunity_product_type_code",
        table_name="pnc_procurement_opportunity_product_type",
    )
    op.drop_table("pnc_procurement_opportunity_product_type")
    op.drop_index(
        "ix_pnc_procurement_opportunity_region_code",
        table_name="pnc_procurement_opportunity",
    )
    op.drop_table("pnc_procurement_opportunity")
