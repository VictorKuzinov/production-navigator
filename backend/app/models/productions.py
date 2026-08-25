# productions.py
## Стандартная библиотека
from typing import TYPE_CHECKING

# Сторонние пакеты
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные пакеты
from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseProfile
    from app.models.equipments import Equipment

class CraneType(Base, PNCBaseReference):
    __tablename__ = "pnc_crane_type"

    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="type_ref",
    )


class TransportType(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_type"

    transports: Mapped[list["Transport"]] = relationship(
        back_populates="type_ref",
    )


class TransportScope(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_scope"

    transports: Mapped[list["Transport"]] = relationship(
        back_populates="scope_ref",
    )


class TransportOwnershipType(Base, PNCBaseReference):
    """Справочник форм владения транспортом PNC"""
    __tablename__ = "pnc_transport_ownership_type"

    transports: Mapped[list["Transport"]] = relationship(
        back_populates="ownership_ref",
    )


class WarehouseType(Base, PNCBaseReference):
    __tablename__ = "pnc_warehouse_type"

    warehouses: Mapped[list["Warehouse"]] = relationship(
        back_populates="type_ref",
    )


class ProductionFacility(Base):
    __tablename__ = "pnc_production_facility"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "facility_name",
            name="uq_pnc_production_facility_profile_name",
        ),
        Index(
            "ix_pnc_production_facility_profile_id",
            "profile_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"),
        nullable=False
    )
    facility_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_area: Mapped[float] = mapped_column(Float, nullable=False)
    available_area: Mapped[float] = mapped_column(Float, nullable=False)
    power_capacity: Mapped[float | None] = mapped_column(Float)
    gas_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    compressed_air: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    water_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steam_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="facilities")
    equipments: Mapped[list["Equipment"]] = relationship(back_populates="facility")
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="facility"
    )


class LiftingEquipment(Base):
    __tablename__ = "pnc_lifting_equipment"
    __table_args__ = (
        Index(
            "ix_pnc_lifting_equipment_profile_type",
            "profile_id",
            "crane_type_code",
        ),
        Index(
            "ix_pnc_lifting_equipment_facility_id",
            "facility_id",
        ),
        Index(
            "ix_pnc_lifting_equipment_warehouse_id",
            "warehouse_id",
        ),
        Index(
            "ix_pnc_lifting_equipment_load_capacity",
            "load_capacity_tons",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"),
        nullable=False,
    )

    crane_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_crane_type.code"),
        nullable=False,
    )

    facility_id: Mapped[int | None] = mapped_column(
        ForeignKey("pnc_production_facility.id"),
        nullable=True,
    )

    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("pnc_warehouse.id"),
        nullable=True,
    )

    load_capacity_tons: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    max_lift_height: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="lifting_equipments",
    )

    type_ref: Mapped["CraneType"] = relationship(
        back_populates="lifting_equipments",
    )

    facility: Mapped["ProductionFacility | None"] = relationship(
        back_populates="lifting_equipments",
    )

    warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="lifting_equipments",
    )


class Warehouse(Base):
    __tablename__ = "pnc_warehouse"
    __table_args__ = (
        Index(
            "ix_pnc_warehouse_profile_type",
            "profile_id",
            "warehouse_type_code",
        ),
    )
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"),
        nullable=False
    )
    warehouse_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_warehouse_type.code"), nullable=False
    )
    total_capacity_cube: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    max_load_sqm: Mapped[float | None] = mapped_column(Float)
    temperature_control: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="warehouses"
    )
    type_ref: Mapped["WarehouseType"] = relationship(
        back_populates="warehouses"
    )
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="warehouse"
    )


class Transport(Base):
    __tablename__ = "pnc_transport"
    __table_args__ = (
        Index(
            "ix_pnc_transport_profile_type",
            "profile_id", "transport_type_code"
        ),
        Index(
            "ix_pnc_transport_profile_scope",
            "profile_id",
            "transport_scope_code"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey(
            "pnc_enterprise_profile.id"
        ),
        nullable=False
    )
    transport_type_code: Mapped[str] = mapped_column(
        ForeignKey(
            "pnc_transport_type.code"
        ),
        nullable=False
    )
    transport_scope_code: Mapped[str] = mapped_column(
        ForeignKey(
            "pnc_transport_scope.code"
        ),
        nullable=False
    )
    transport_ownership_code: Mapped[str] = mapped_column(
        ForeignKey(
            "pnc_transport_ownership_type.code"
        ),
        nullable=False
    )
    payload_tons: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    body_volume_cube: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    has_refrigeration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="transports"
    )
    type_ref: Mapped["TransportType"] = relationship(
        back_populates="transports"
    )
    scope_ref: Mapped["TransportScope"] = relationship(
        back_populates="transports"
    )
    ownership_ref: Mapped["TransportOwnershipType"] = relationship(
        back_populates="transports"
    )
