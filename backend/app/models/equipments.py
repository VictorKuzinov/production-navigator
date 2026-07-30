
# Сторонние пакеты
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    id: Mapped[int] = mapped_column(primary_key=True)

    equipments: Mapped[list["Equipment"]] = relationship(back_populates="type_ref")

class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        Index(
            "ix_equipment_profile_type",
            "profile_id",
            "equipment_type_code"
        ),
        Index(
            "ix_equipment_facility_type",
            "facility_id",
            "equipment_type_code"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_profile.id"),
        nullable=False
    )
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("production_facility.id"),
        nullable=False)
    equipment_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_equipment_type.code"),
        nullable=False
    )
    cnc: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    axes: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    max_diameter: Mapped[float | None] = mapped_column(Float)
    working_zone_x: Mapped[float | None] = mapped_column(Float)
    working_zone_y: Mapped[float | None] = mapped_column(Float)
    working_zone_z: Mapped[float | None] = mapped_column(Float)

    type_ref: Mapped["EquipmentType"] = relationship(
        back_populates="equipments"
    )

