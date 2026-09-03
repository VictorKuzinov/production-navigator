from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.enterprises import CertificateType, Region
    from app.models.equipments import EquipmentType
    from app.models.materials import Material, MaterialGroup
    from app.models.pnc_reference import TechnologyType
    from app.models.products import ProductType


class ProcurementOpportunityStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    AWARDED = "AWARDED"
    UNKNOWN = "UNKNOWN"


class RequirementStrength(StrEnum):
    MANDATORY = "MANDATORY"
    PREFERRED = "PREFERRED"
    UNKNOWN = "UNKNOWN"


class RequirementCollectionState(StrEnum):
    UNKNOWN = "UNKNOWN"
    KNOWN = "KNOWN"


class ProcurementOpportunity(Base):
    __tablename__ = "pnc_procurement_opportunity"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_pnc_procurement_opportunity_identity",
        ),
        CheckConstraint(
            "source = trim(source) AND source = lower(source) "
            "AND length(source) > 0",
            name="ck_pnc_procurement_opportunity_source_nonblank_lower",
        ),
        CheckConstraint(
            "external_id = trim(external_id) AND length(external_id) > 0",
            name="ck_pnc_procurement_opportunity_external_id_nonblank_trimmed",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_pnc_procurement_opportunity_title_nonblank",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'CANCELLED', 'AWARDED', 'UNKNOWN')",
            name="ck_pnc_procurement_opportunity_status",
        ),
        CheckConstraint(
            "price_amount IS NULL OR price_currency IS NOT NULL",
            name="ck_pnc_procurement_opportunity_price_currency_required",
        ),
        CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0",
            name="ck_pnc_procurement_opportunity_price_nonnegative",
        ),
        CheckConstraint(
            "quantity IS NULL OR unit IS NOT NULL",
            name="ck_pnc_procurement_opportunity_quantity_unit_required",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_pnc_procurement_opportunity_quantity_positive",
        ),
        CheckConstraint(
            "NOT (application_deadline_date IS NOT NULL "
            "AND application_deadline_at IS NOT NULL)",
            name="ck_pnc_procurement_opportunity_application_deadline_shape",
        ),
        CheckConstraint(
            "NOT (execution_deadline_date IS NOT NULL "
            "AND execution_deadline_at IS NOT NULL)",
            name="ck_pnc_procurement_opportunity_execution_deadline_shape",
        ),
        CheckConstraint(
            "product_type_codes_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_product_types_state",
        ),
        CheckConstraint(
            "material_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_materials_state",
        ),
        CheckConstraint(
            "technology_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_technologies_state",
        ),
        CheckConstraint(
            "equipment_requirements_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_equipment_state",
        ),
        CheckConstraint(
            "required_certificates_state IN ('UNKNOWN', 'KNOWN')",
            name="ck_pnc_procurement_opportunity_certificates_state",
        ),
        Index("ix_pnc_procurement_opportunity_region_code", "region_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    procurement_number: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    customer: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[ProcurementOpportunityStatus] = mapped_column(
        String(16),
        nullable=False,
    )
    procurement_type: Mapped[str | None] = mapped_column(String(50))

    okpd2_codes: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True),
    )
    product_type_codes_state: Mapped[RequirementCollectionState] = mapped_column(
        String(7),
        nullable=False,
    )
    material_requirements_state: Mapped[RequirementCollectionState] = mapped_column(
        String(7),
        nullable=False,
    )
    technology_requirements_state: Mapped[RequirementCollectionState] = mapped_column(
        String(7), nullable=False
    )
    equipment_requirements_state: Mapped[RequirementCollectionState] = mapped_column(
        String(7), nullable=False
    )
    required_certificates_state: Mapped[RequirementCollectionState] = mapped_column(
        String(7),
        nullable=False,
    )
    dimensional_mass_requirements: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    quality_requirements: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True),
    )

    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    price_currency: Mapped[str | None] = mapped_column(String(3))
    region_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_region.code", ondelete="RESTRICT"),
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(32))

    application_deadline_date: Mapped[date | None] = mapped_column(Date)
    application_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    execution_deadline_date: Mapped[date | None] = mapped_column(Date)
    execution_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    region: Mapped["Region | None"] = relationship()
    product_types: Mapped[list["ProcurementOpportunityProductType"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: ProcurementOpportunityProductType.product_type_code,
    )
    material_requirements: Mapped[list["ProcurementMaterialRequirement"]] = (
        relationship(
            back_populates="opportunity",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by=lambda: (
                ProcurementMaterialRequirement.material_group_code,
                ProcurementMaterialRequirement.material_id,
            ),
        )
    )
    technology_requirements: Mapped[list["ProcurementTechnologyRequirement"]] = (
        relationship(
            back_populates="opportunity",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by=lambda: ProcurementTechnologyRequirement.technology_code,
        )
    )
    equipment_requirements: Mapped[list["ProcurementEquipmentRequirement"]] = (
        relationship(
            back_populates="opportunity",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by=lambda: ProcurementEquipmentRequirement.equipment_type_code,
        )
    )
    certificate_requirements: Mapped[list["ProcurementCertificateRequirement"]] = (
        relationship(
            back_populates="opportunity",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by=lambda: ProcurementCertificateRequirement.certificate_type_code,
        )
    )


class ProcurementOpportunityProductType(Base):
    __tablename__ = "pnc_procurement_opportunity_product_type"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "product_type_code",
            name="uq_pnc_procurement_opportunity_product_type_target",
        ),
        Index(
            "ix_pnc_procurement_opportunity_product_type_code",
            "product_type_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_procurement_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_product_type.code", ondelete="RESTRICT"),
        nullable=False,
    )

    opportunity: Mapped[ProcurementOpportunity] = relationship(
        back_populates="product_types",
    )
    product_type: Mapped["ProductType"] = relationship()


class ProcurementMaterialRequirement(Base):
    __tablename__ = "pnc_procurement_material_requirement"
    __table_args__ = (
        CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_material_requirement_strength",
        ),
        Index(
            "uq_pnc_procurement_material_requirement_group_target",
            "opportunity_id",
            "material_group_code",
            unique=True,
            postgresql_where=text("material_id IS NULL"),
            sqlite_where=text("material_id IS NULL"),
        ),
        Index(
            "uq_pnc_procurement_material_requirement_material_target",
            "opportunity_id",
            "material_id",
            unique=True,
            postgresql_where=text("material_id IS NOT NULL"),
            sqlite_where=text("material_id IS NOT NULL"),
        ),
        Index(
            "ix_pnc_procurement_material_requirement_group_code",
            "material_group_code",
        ),
        Index(
            "ix_pnc_procurement_material_requirement_material_id",
            "material_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_procurement_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_group_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_material_group.code", ondelete="RESTRICT"),
        nullable=False,
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("pnc_material.id", ondelete="RESTRICT"),
    )
    requirement_strength: Mapped[RequirementStrength] = mapped_column(
        String(12),
        nullable=False,
    )

    opportunity: Mapped[ProcurementOpportunity] = relationship(
        back_populates="material_requirements",
    )
    material_group: Mapped["MaterialGroup"] = relationship(
        foreign_keys=[material_group_code],
    )
    material: Mapped["Material | None"] = relationship(
        foreign_keys=[material_id],
    )


class ProcurementTechnologyRequirement(Base):
    __tablename__ = "pnc_procurement_technology_requirement"
    __table_args__ = (
        CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_technology_requirement_strength",
        ),
        UniqueConstraint(
            "opportunity_id",
            "technology_code",
            name="uq_pnc_procurement_technology_requirement_target",
        ),
        Index(
            "ix_pnc_procurement_technology_requirement_technology_code",
            "technology_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_procurement_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    technology_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_technology_type.code", ondelete="RESTRICT"),
        nullable=False,
    )
    requirement_strength: Mapped[RequirementStrength] = mapped_column(
        String(12),
        nullable=False,
    )

    opportunity: Mapped[ProcurementOpportunity] = relationship(
        back_populates="technology_requirements",
    )
    technology: Mapped["TechnologyType"] = relationship()


class ProcurementEquipmentRequirement(Base):
    __tablename__ = "pnc_procurement_equipment_requirement"
    __table_args__ = (
        CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_equipment_requirement_strength",
        ),
        CheckConstraint(
            "axes IS NULL OR axes >= 1",
            name="ck_pnc_procurement_equipment_requirement_axes",
        ),
        CheckConstraint(
            "working_zone_x_mm IS NULL OR working_zone_x_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_x_positive",
        ),
        CheckConstraint(
            "working_zone_y_mm IS NULL OR working_zone_y_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_y_positive",
        ),
        CheckConstraint(
            "working_zone_z_mm IS NULL OR working_zone_z_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_zone_z_positive",
        ),
        CheckConstraint(
            "diameter_mm IS NULL OR diameter_mm > 0",
            name="ck_pnc_procurement_equipment_requirement_diameter_positive",
        ),
        UniqueConstraint(
            "opportunity_id",
            "equipment_type_code",
            name="uq_pnc_procurement_equipment_requirement_target",
        ),
        Index(
            "ix_pnc_procurement_equipment_requirement_equipment_type_code",
            "equipment_type_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_procurement_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_equipment_type.code", ondelete="RESTRICT"),
        nullable=False,
    )
    cnc: Mapped[bool | None] = mapped_column(Boolean)
    axes: Mapped[int | None] = mapped_column(Integer)
    working_zone_x_mm: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    working_zone_y_mm: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    working_zone_z_mm: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    diameter_mm: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    requirement_strength: Mapped[RequirementStrength] = mapped_column(
        String(12),
        nullable=False,
    )

    opportunity: Mapped[ProcurementOpportunity] = relationship(
        back_populates="equipment_requirements",
    )
    equipment_type: Mapped["EquipmentType"] = relationship()


class ProcurementCertificateRequirement(Base):
    __tablename__ = "pnc_procurement_certificate_requirement"
    __table_args__ = (
        CheckConstraint(
            "requirement_strength IN ('MANDATORY', 'PREFERRED', 'UNKNOWN')",
            name="ck_pnc_procurement_certificate_requirement_strength",
        ),
        UniqueConstraint(
            "opportunity_id",
            "certificate_type_code",
            name="uq_pnc_procurement_certificate_requirement_target",
        ),
        Index(
            "ix_pnc_procurement_certificate_requirement_type_code",
            "certificate_type_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_procurement_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    certificate_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_certificate_type.code", ondelete="RESTRICT"),
        nullable=False,
    )
    requirement_strength: Mapped[RequirementStrength] = mapped_column(
        String(12),
        nullable=False,
    )
    required_by: Mapped[date | None] = mapped_column(Date)
    valid_through: Mapped[date | None] = mapped_column(Date)

    opportunity: Mapped[ProcurementOpportunity] = relationship(
        back_populates="certificate_requirements",
    )
    certificate_type: Mapped["CertificateType"] = relationship()
