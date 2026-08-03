# products.py
# Стандартные библиотеки
from typing import TYPE_CHECKING

# Сторонние пакеты
from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные
from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseProfile
    from app.models.materials import MaterialItem

class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"

    products: Mapped[list["Product"]] = relationship(
        back_populates="type_ref"
    )

class Product(Base):
    __tablename__ = "pnc_product"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "sku_code",
            name="uq_pnc_product_profile_sku"
        ),
        Index(
            "ix_pnc_product_profile_type",
            "profile_id",
            "product_type_code"
        ),
        Index(
            "ix_pnc_product_material_item_id",
            "material_item_id"
        ),
        Index(
            "ix_pnc_product_name",
            "name"
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
    product_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_product_type.code"),
        nullable=False
    )
    material_item_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_material_item.id"),
        nullable=False
    )
    sku_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    weight_net: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    required_it_grade: Mapped[int | None] = mapped_column(Integer)
    required_ra: Mapped[float | None] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="products"
    )
    type_ref: Mapped["ProductType"] = relationship(
        back_populates="products"
    )
    material_item: Mapped["MaterialItem"] = relationship(
        back_populates="products"
    )
    # orders: Mapped[list["ProductionOrder"]] = relationship(
    #     back_populates="product"
    # )
