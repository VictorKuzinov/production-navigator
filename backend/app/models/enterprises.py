# enterprises.py
## Стандартная библиотека
from typing import Optional

# Сторонние пакеты
from sqlalchemy import (
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


class CertificateType(Base, PNCBaseReference):
    __tablename__ = "pnc_certificate_type"


class Industry(Base, PNCBaseReference):
    __tablename__ = "pnc_industry"


class CompanySize(Base, PNCBaseReference):
    __tablename__ = "pnc_company_size"


class Region(Base, PNCBaseReference):
    __tablename__ = "pnc_region"


class EnterpriseProfile(Base):
    __tablename__ = "pnc_enterprise_profile"
    __table_args__ = (
        UniqueConstraint("inn", name="uq_pnc_enterprise_profile_inn"),
        UniqueConstraint("ogrn", name="uq_pnc_enterprise_profile_ogrn"),
        Index("ix_pnc_enterprise_profile_region_code", "region_code"),
        Index("ix_pnc_enterprise_profile_company_size_code", "company_size_code"),
        Index("ix_pnc_enterprise_profile_company_name", "company_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ИНН и ОГРН хранятся строками: это идентификаторы, а не числа для вычислений.
    inn: Mapped[Optional[str]] = mapped_column(String(12))
    ogrn: Mapped[Optional[str]] = mapped_column(String(15))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    employees_count: Mapped[Optional[int]] = mapped_column(Integer)
    company_size_code: Mapped[Optional[str]] = mapped_column(
        ForeignKey("pnc_company_size.code")
    )
    region_code: Mapped[Optional[str]] = mapped_column(ForeignKey("pnc_region.code"))

    size_ref: Mapped[Optional["CompanySize"]] = relationship(back_populates="profiles")
    region_ref: Mapped[Optional["Region"]] = relationship(back_populates="profiles")
    # facilities: Mapped[List["ProductionFacility"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # warehouses: Mapped[List["Warehouse"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # lifting_equipments: Mapped[List["LiftingEquipment"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # transports: Mapped[List["Transport"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # equipments: Mapped[List["Equipment"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # products: Mapped[List["Product"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # industries: Mapped[list["EnterpriseIndustry"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # orders: Mapped[list["ProductionOrder"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan"
    # )
    # quality_capability: Mapped[Optional["QualityCapability"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan", single_parent=True
    # )
