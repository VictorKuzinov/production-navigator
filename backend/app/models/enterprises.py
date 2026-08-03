# enterprises.py
# Стандартные библиотеки
from datetime import date
from typing import TYPE_CHECKING, Optional

# Сторонние пакеты
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные пакеты
from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.equipments import Equipment
    from app.models.orders import ProductionOrder
    from app.models.productions import (
        LiftingEquipment,
        ProductionFacility,
        Transport,
        Warehouse,
    )
    from app.models.products import Product


class CertificateType(Base, PNCBaseReference):
    __tablename__ = "pnc_certificate_type"

    certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
        back_populates="type_ref",
    )

class Industry(Base, PNCBaseReference):
    __tablename__ = "pnc_industry"

    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="industry_ref",
    )

    enterprise_links: Mapped[list["EnterpriseIndustry"]] = relationship(
        back_populates="industry_ref",
    )


class CompanySize(Base, PNCBaseReference):
    __tablename__ = "pnc_company_size"

    profiles: Mapped[list["EnterpriseProfile"]] = relationship(
        back_populates="size_ref"
    )


class Region(Base, PNCBaseReference):
    __tablename__ = "pnc_region"

    profiles: Mapped[list["EnterpriseProfile"]] = relationship(
        back_populates="region_ref",
    )


class EnterpriseProfile(Base):
    __tablename__ = "pnc_enterprise_profile"
    __table_args__ = (
        UniqueConstraint(
            "inn",
            name="uq_pnc_enterprise_profile_inn"
        ),
        UniqueConstraint(
            "ogrn",
            name="uq_pnc_enterprise_profile_ogrn"
        ),
        Index(
            "ix_pnc_enterprise_profile_region_code",
            "region_code"
        ),
        Index(
            "ix_pnc_enterprise_profile_company_size_code",
            "company_size_code"
        ),
        Index(
            "ix_pnc_enterprise_profile_company_name",
            "company_name"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    # ИНН и ОГРН хранятся строками: это идентификаторы, а не числа для вычислений.
    inn: Mapped[str | None] = mapped_column(String(12))
    ogrn: Mapped[str | None] = mapped_column(String(15))
    website: Mapped[str | None] = mapped_column(String(255))
    employees_count: Mapped[int | None] = mapped_column(Integer)
    company_size_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_company_size.code")
    )
    region_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_region.code")
    )

    size_ref: Mapped[Optional["CompanySize"]] = relationship(
        back_populates="profiles"
    )
    region_ref: Mapped[Optional["Region"]] = relationship(
        back_populates="profiles"
    )
    facilities: Mapped[list["ProductionFacility"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    warehouses: Mapped[list["Warehouse"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    transports: Mapped[list["Transport"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    industries: Mapped[list["EnterpriseIndustry"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan"
    )
    # quality_capability: Mapped[Optional["QualityCapability"]] = relationship(
    #     back_populates="profile", cascade="all, delete-orphan", single_parent=True
    # )


class EnterpriseCertificate(Base):
    __tablename__ = "pnc_enterprise_certificate"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "certificate_type_code",
            "issue_date",
            "expiry_date",
            name="uq_pnc_certificate_profile_type_dates",
        ),
        Index(
            "ix_pnc_certificate_profile_type_expiry",
            "profile_id",
            "certificate_type_code",
            "expiry_date",
        ),
        Index(
            "ix_pnc_certificate_expiry_date",
            "expiry_date",
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
    certificate_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_certificate_type.code"),
        nullable=False,
    )
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    expiry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="certificates",
    )
    type_ref: Mapped["CertificateType"] = relationship(
        back_populates="certificates",
    )

class EnterpriseIndustry(Base):
    __tablename__ = "pnc_enterprise_industry"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "industry_code",
            name="uq_pnc_enterprise_industry_profile_industry"
        ),
        Index(
            "ix_pnc_enterprise_industry_primary",
            "profile_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE"),
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
    industry_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_industry.code"),
        nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="industries"
    )
    industry_ref: Mapped["Industry"] = relationship(
        back_populates="enterprise_links"
    )
