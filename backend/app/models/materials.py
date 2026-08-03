# materiald.py
## Стандартные библиотеки

# Сторонние пакеты
from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base_reference import PNCBaseReference
from app.models.products import Product


class MaterialGroup(Base, PNCBaseReference):
    __tablename__ = "pnc_material_group"

    materials: Mapped[list["Material"]] = relationship(
        back_populates="group_ref"
    )


class MaterialForm(Base, PNCBaseReference):
    __tablename__ = "pnc_material_form"

    material_items: Mapped[list["MaterialItem"]] = relationship(
        back_populates="form_ref"
    )



class Material(Base):
    __tablename__ = "pnc_material"
    __table_args__ = (
        UniqueConstraint(
            "group_code",
            "grade_name",
            name="uq_pnc_material_group_grade"
        ),
        Index(
            "ix_pnc_material_group_code",
            "group_code"
        ),
        Index(
            "ix_pnc_material_grade_name",
            "grade_name"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    group_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_material_group.code"),
        nullable=False
    )
    grade_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    density: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    group_ref: Mapped["MaterialGroup"] = relationship(
        back_populates="materials"
    )
    items: Mapped[list["MaterialItem"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan"
    )


class MaterialItem(Base):
    __tablename__ = "pnc_material_item"
    __table_args__ = (
        UniqueConstraint(
            "material_id",
            "material_form_code",
            "dimension_1",
            "unit_of_measure",
            name="uq_pnc_material_item_form_dimension_unit",
        ),
        Index(
            "ix_pnc_material_item_material_form",
            "material_id",
            "material_form_code"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_material.id"),
        nullable=False
    )
    material_form_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_material_form.code"),
        nullable=False
    )
    dimension_1: Mapped[float | None] = mapped_column(Float)
    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    material: Mapped["Material"] = relationship(
        back_populates="items"
    )
    form_ref: Mapped["MaterialForm"] = relationship(
        back_populates="material_items"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="material_item"
    )
