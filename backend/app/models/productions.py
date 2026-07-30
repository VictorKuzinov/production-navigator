# productions.py
## Стандартная библиотека

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
from app.models.enterprises import EnterpriseProfile


class CraneType(Base, PNCBaseReference):
    __tablename__ = "pnc_crane_type"


class TransportType(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_type"


class TransportScope(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_scope"


class TransportOwnershipType(Base, PNCBaseReference):
    """Справочник форм владения транспортом PNC"""
    __tablename__ = "pnc_transport_ownership_type"


class WarehouseType(Base, PNCBaseReference):
    __tablename__ = "pnc_warehouse_type"


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
    # equipments: Mapped[list["Equipment"]] = relationship(back_populates="facility")
    # lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
    #     back_populates="facility"
    # )
