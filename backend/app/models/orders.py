# orders.py
## Стандартная библиотека
from datetime import date
from typing import TYPE_CHECKING

# Сторонние пакеты
from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные
from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseProfile, Industry
    from app.models.products import Product



class OrderType(Base, PNCBaseReference):
    __tablename__ = "pnc_order_type"

    orders: Mapped[list["ProductionOrder"]] = relationship(back_populates="type_ref")


class ProductionOrder(Base):
    __tablename__ = "pnc_production_order"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "order_number",
            name="uq_pnc_order_profile_number"
        ),
        Index(
            "ix_pnc_order_profile_deadline",
            "profile_id",
            "deadline"
        ),
        Index(
            "ix_pnc_order_type_deadline",
            "order_type_code",
            "deadline"
        ),
        Index(
            "ix_pnc_order_industry_deadline",
            "industry_code",
            "deadline"
        ),
        Index(
            "ix_pnc_order_product_id",
            "product_id"
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
    order_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_order_type.code"),
        nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_product.id"),
        nullable=False
    )
    industry_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_industry.code"),
        nullable=False
    )
    order_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    deadline: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="orders"
    )
    type_ref: Mapped["OrderType"] = relationship(
        back_populates="orders"
    )
    product: Mapped["Product"] = relationship(
        back_populates="orders"
    )
    industry_ref: Mapped["Industry"] = relationship(
        back_populates="orders"
    )