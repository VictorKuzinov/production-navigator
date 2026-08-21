# Модели SQLAlchemy

## Назначение документа

Документ фиксирует целевую ORM-модель проекта «Производственный навигатор». Все таблицы предметной области используют префикс `pnc_`; имена ограничений и индексов приведены к тому же соглашению. Наличие модели в целевой документации не заменяет проверку фактического кода и миграций перед внедрением.

## Статус реализации и граница документа

В целевую модель входят корпоративные справочники PNC, внешний иерархический классификатор `OKVED`, основные сущности и связи производственного профиля. `OKVED` не наследует `PNCBaseReference`.

Целевая документация и состояние реализации — разные вещи. Приведённый ниже
код задаёт согласованную целевую ORM, но не доказывает, что каждая модель
закоммичена, каждая миграция проверена и применена к конкретной базе данных.

Снимок рабочего дерева на 2026-08-14:

| Область | Целевая документация | Наблюдаемое состояние backend | Интерпретация |
|---------|-----------------------|-------------------------------|--------------|
| Корпоративные PNC-справочники | Описаны | ORM-модели и соответствующие миграции присутствуют | Наличие файлов не заменяет проверку состояния БД |
| Основные сущности производственного профиля | Описаны | ORM-модели и миграции присутствуют | Готовность конкретного развёртывания этим документом не подтверждается |
| `OKVED` и `EnterpriseOKVED` | Входят в целевую модель | Модели и кандидатная миграция присутствуют в незакоммиченном рабочем дереве | Изменения нельзя считать завершёнными только по наличию файлов |

Основные сущности целевой модели: `EnterpriseProfile`, `ProductionFacility`, `Equipment`, `Warehouse`, `LiftingEquipment`, `Transport`, `Material`, `MaterialItem`, `Product`, `ProductionOrder`, `EnterpriseCertificate`, `EnterpriseIndustry`, `EnterpriseOKVED` и `QualityCapability`.

## Целевая ORM-модель

Код ниже отражает целевые таблицы, ограничения, индексы и двусторонние связи. Для обычных типов используются современные аннотации `T | None` и `list[T]`. Для ссылок на классы, объявленные ниже, вся аннотация помещается в строку; это не допускает вычисления выражения вида `"ClassName" | None` во время импорта.

```python
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PNCBaseReference:
    __abstract__ = True

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    ics_section: Mapped[str | None] = mapped_column(String(50))
    ref_system: Mapped[str] = mapped_column(String(100), nullable=False)
    ref_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class OKVED(Base):
    """Локальное иерархическое представление внешнего классификатора ОКВЭД."""

    __tablename__ = "pnc_okved"
    __table_args__ = (
        Index("ix_pnc_okved_parent_code", "parent_code"),
    )

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_okved.code")
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)

    children: Mapped[list["OKVED"]] = relationship(back_populates="parent")
    parent: Mapped["OKVED | None"] = relationship(
        back_populates="children",
        remote_side=[code],
    )
    enterprises: Mapped[list["EnterpriseOKVED"]] = relationship(
        back_populates="okved"
    )


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    equipments: Mapped[list["Equipment"]] = relationship(back_populates="type_ref")


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"


class MaterialGroup(Base, PNCBaseReference):
    __tablename__ = "pnc_material_group"

    materials: Mapped[list["Material"]] = relationship(back_populates="group_ref")


class MaterialForm(Base, PNCBaseReference):
    __tablename__ = "pnc_material_form"

    material_items: Mapped[list["MaterialItem"]] = relationship(
        back_populates="form_ref"
    )


class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"

    products: Mapped[list["Product"]] = relationship(back_populates="type_ref")


class CraneType(Base, PNCBaseReference):
    __tablename__ = "pnc_crane_type"

    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="type_ref"
    )


class TransportType(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_type"

    transports: Mapped[list["Transport"]] = relationship(back_populates="type_ref")


class TransportScope(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_scope"

    transports: Mapped[list["Transport"]] = relationship(back_populates="scope_ref")


class TransportOwnershipType(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_ownership_type"

    transports: Mapped[list["Transport"]] = relationship(
        back_populates="ownership_ref"
    )


class WarehouseType(Base, PNCBaseReference):
    __tablename__ = "pnc_warehouse_type"

    warehouses: Mapped[list["Warehouse"]] = relationship(back_populates="type_ref")


class CertificateType(Base, PNCBaseReference):
    __tablename__ = "pnc_certificate_type"

    certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
        back_populates="type_ref"
    )


class Industry(Base, PNCBaseReference):
    __tablename__ = "pnc_industry"

    enterprise_links: Mapped[list["EnterpriseIndustry"]] = relationship(
        back_populates="industry_ref"
    )
    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="industry_ref"
    )


class OrderType(Base, PNCBaseReference):
    __tablename__ = "pnc_order_type"

    orders: Mapped[list["ProductionOrder"]] = relationship(back_populates="type_ref")


class CompanySize(Base, PNCBaseReference):
    __tablename__ = "pnc_company_size"

    profiles: Mapped[list["EnterpriseProfile"]] = relationship(
        back_populates="size_ref"
    )


class Region(Base, PNCBaseReference):
    __tablename__ = "pnc_region"

    profiles: Mapped[list["EnterpriseProfile"]] = relationship(
        back_populates="region_ref"
    )


class EnterpriseProfile(Base):
    __tablename__ = "pnc_enterprise_profile"
    __table_args__ = (
        UniqueConstraint("inn", name="uq_pnc_enterprise_profile_inn"),
        UniqueConstraint("ogrn", name="uq_pnc_enterprise_profile_ogrn"),
        Index("ix_pnc_enterprise_profile_region_code", "region_code"),
        Index(
            "ix_pnc_enterprise_profile_company_size_code",
            "company_size_code",
        ),
        Index("ix_pnc_enterprise_profile_company_name", "company_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12))
    ogrn: Mapped[str | None] = mapped_column(String(15))
    website: Mapped[str | None] = mapped_column(String(255))
    employees_count: Mapped[int | None] = mapped_column(Integer)
    company_size_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_company_size.code")
    )
    region_code: Mapped[str | None] = mapped_column(ForeignKey("pnc_region.code"))

    size_ref: Mapped["CompanySize | None"] = relationship(back_populates="profiles")
    region_ref: Mapped["Region | None"] = relationship(back_populates="profiles")
    facilities: Mapped[list["ProductionFacility"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    warehouses: Mapped[list["Warehouse"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    transports: Mapped[list["Transport"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    industries: Mapped[list["EnterpriseIndustry"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    okveds: Mapped[list["EnterpriseOKVED"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    quality_capability: Mapped["QualityCapability | None"] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        single_parent=True,
    )


class ProductionFacility(Base):
    __tablename__ = "pnc_production_facility"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "facility_name",
            name="uq_pnc_production_facility_profile_name",
        ),
        Index("ix_pnc_production_facility_profile_id", "profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    facility_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_area: Mapped[float] = mapped_column(Float, nullable=False)
    available_area: Mapped[float] = mapped_column(Float, nullable=False)
    power_capacity: Mapped[float | None] = mapped_column(Float)
    gas_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    compressed_air: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    water_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steam_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="facilities")
    equipments: Mapped[list["Equipment"]] = relationship(back_populates="facility")
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="facility"
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    warehouse_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_warehouse_type.code"), nullable=False
    )
    total_capacity_cube: Mapped[float] = mapped_column(Float, nullable=False)
    max_load_sqm: Mapped[float | None] = mapped_column(Float)
    temperature_control: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="warehouses")
    type_ref: Mapped["WarehouseType"] = relationship(back_populates="warehouses")
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="warehouse"
    )


class LiftingEquipment(Base):
    __tablename__ = "pnc_lifting_equipment"
    __table_args__ = (
        Index(
            "ix_pnc_lifting_equipment_profile_type",
            "profile_id",
            "crane_type_code",
        ),
        Index("ix_pnc_lifting_equipment_facility_id", "facility_id"),
        Index("ix_pnc_lifting_equipment_warehouse_id", "warehouse_id"),
        Index("ix_pnc_lifting_equipment_load_capacity", "load_capacity_tons"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    crane_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_crane_type.code"), nullable=False
    )
    facility_id: Mapped[int | None] = mapped_column(
        ForeignKey("pnc_production_facility.id")
    )
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("pnc_warehouse.id"))
    load_capacity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    max_lift_height: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="lifting_equipments"
    )
    type_ref: Mapped["CraneType"] = relationship(
        back_populates="lifting_equipments"
    )
    facility: Mapped["ProductionFacility | None"] = relationship(
        back_populates="lifting_equipments"
    )
    warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="lifting_equipments"
    )


class Transport(Base):
    __tablename__ = "pnc_transport"
    __table_args__ = (
        Index(
            "ix_pnc_transport_profile_type", "profile_id", "transport_type_code"
        ),
        Index(
            "ix_pnc_transport_profile_scope", "profile_id", "transport_scope_code"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    transport_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_transport_type.code"), nullable=False
    )
    transport_scope_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_transport_scope.code"), nullable=False
    )
    transport_ownership_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_transport_ownership_type.code"), nullable=False
    )
    payload_tons: Mapped[float] = mapped_column(Float, nullable=False)
    body_volume_cube: Mapped[float | None] = mapped_column(Float)
    has_refrigeration: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="transports")
    type_ref: Mapped["TransportType"] = relationship(back_populates="transports")
    scope_ref: Mapped["TransportScope"] = relationship(back_populates="transports")
    ownership_ref: Mapped["TransportOwnershipType"] = relationship(
        back_populates="transports"
    )


class Equipment(Base):
    __tablename__ = "pnc_equipment"
    __table_args__ = (
        Index(
            "ix_pnc_equipment_profile_type", "profile_id", "equipment_type_code"
        ),
        Index(
            "ix_pnc_equipment_facility_type", "facility_id", "equipment_type_code"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_production_facility.id"), nullable=False
    )
    equipment_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_equipment_type.code"), nullable=False
    )
    model_name: Mapped[str | None] = mapped_column(String(255))
    cnc: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    axes: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_diameter: Mapped[float | None] = mapped_column(Float)
    working_zone_x: Mapped[float | None] = mapped_column(Float)
    working_zone_y: Mapped[float | None] = mapped_column(Float)
    working_zone_z: Mapped[float | None] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="equipments")
    facility: Mapped["ProductionFacility"] = relationship(back_populates="equipments")
    type_ref: Mapped["EquipmentType"] = relationship(back_populates="equipments")


class QualityCapability(Base):
    __tablename__ = "pnc_quality_capability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"),
        nullable=False,
        unique=True,
    )
    min_it_grade: Mapped[int | None] = mapped_column(Integer)
    min_ra: Mapped[float | None] = mapped_column(Float)
    measuring_tools: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    cim_machine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="quality_capability"
    )


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
        Index("ix_pnc_certificate_expiry_date", "expiry_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    certificate_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_certificate_type.code"), nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="certificates")
    type_ref: Mapped["CertificateType"] = relationship(
        back_populates="certificates"
    )


class EnterpriseIndustry(Base):
    __tablename__ = "pnc_enterprise_industry"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "industry_code",
            name="uq_pnc_enterprise_industry_profile_industry",
        ),
        Index(
            "ix_pnc_enterprise_industry_primary",
            "profile_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    industry_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_industry.code"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="industries")
    industry_ref: Mapped["Industry"] = relationship(
        back_populates="enterprise_links"
    )


class EnterpriseOKVED(Base):
    __tablename__ = "pnc_enterprise_okved"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "okved_code",
            name="uq_enterprise_okved",
        ),
        Index("ix_pnc_enterprise_okved_code", "okved_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    okved_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_okved.code"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="okveds")
    okved: Mapped["OKVED"] = relationship(back_populates="enterprises")


class Material(Base):
    __tablename__ = "pnc_material"
    __table_args__ = (
        UniqueConstraint(
            "group_code", "grade_name", name="uq_pnc_material_group_grade"
        ),
        Index("ix_pnc_material_group_code", "group_code"),
        Index("ix_pnc_material_grade_name", "grade_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_material_group.code"), nullable=False
    )
    grade_name: Mapped[str] = mapped_column(String(100), nullable=False)
    density: Mapped[float | None] = mapped_column(Float)

    group_ref: Mapped["MaterialGroup"] = relationship(back_populates="materials")
    items: Mapped[list["MaterialItem"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
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
            "material_form_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_material.id"), nullable=False
    )
    material_form_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_material_form.code"), nullable=False
    )
    dimension_1: Mapped[float | None] = mapped_column(Float)
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False)

    material: Mapped["Material"] = relationship(back_populates="items")
    form_ref: Mapped["MaterialForm"] = relationship(
        back_populates="material_items"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="material_item"
    )


class Product(Base):
    __tablename__ = "pnc_product"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "sku_code", name="uq_pnc_product_profile_sku"
        ),
        Index("ix_pnc_product_profile_type", "profile_id", "product_type_code"),
        Index("ix_pnc_product_material_item_id", "material_item_id"),
        Index("ix_pnc_product_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    product_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_product_type.code"), nullable=False
    )
    material_item_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_material_item.id"), nullable=False
    )
    sku_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight_net: Mapped[float] = mapped_column(Float, nullable=False)
    required_it_grade: Mapped[int | None] = mapped_column(Integer)
    required_ra: Mapped[float | None] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="products")
    type_ref: Mapped["ProductType"] = relationship(back_populates="products")
    material_item: Mapped["MaterialItem"] = relationship(back_populates="products")
    orders: Mapped[list["ProductionOrder"]] = relationship(back_populates="product")


class ProductionOrder(Base):
    __tablename__ = "pnc_production_order"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "order_number", name="uq_pnc_order_profile_number"
        ),
        Index("ix_pnc_order_profile_deadline", "profile_id", "deadline"),
        Index("ix_pnc_order_type_deadline", "order_type_code", "deadline"),
        Index("ix_pnc_order_industry_deadline", "industry_code", "deadline"),
        Index("ix_pnc_order_product_id", "product_id"),
        Index("ix_pnc_order_deadline", "deadline"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False
    )
    order_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_order_type.code"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("pnc_product.id"), nullable=False)
    industry_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_industry.code"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="orders")
    type_ref: Mapped["OrderType"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")
    industry_ref: Mapped["Industry"] = relationship(back_populates="orders")
```

## Примечания к ограничениям, индексам и связям

- Все таблицы и вручную именованные индексы/ограничения используют префикс `pnc_`; опечаток вида `ix_pmc_...` и внешних ключей на `pbc_...` в документе нет.
- `Warehouse.__table_args__` — одноэлементный кортеж. Запятая после `Index(...)` обязательна; приведённый вариант синтаксически корректен.
- `EnterpriseIndustry` содержит только PostgreSQL-вариант частичного уникального индекса `ix_pnc_enterprise_industry_primary` с условием `is_primary IS TRUE`. Он гарантирует не более одной основной отрасли на профиль. `sqlite_where` намеренно отсутствует.
- Пара `(profile_id, industry_code)` в `EnterpriseIndustry` защищена ограничением `uq_pnc_enterprise_industry_profile_industry`.
- `EnterpriseIndustry.is_primary` означает основной отраслевой рынок предприятия в терминах PNC. `EnterpriseOKVED.is_primary` означает основной зарегистрированный вид экономической деятельности. Эти признаки имеют разную семантику и не синхронизируются автоматически.
- Пара `(profile_id, okved_code)` в `EnterpriseOKVED` защищена ограничением `uq_enterprise_okved`. Текущая целевая схема не содержит частичного уникального индекса, ограничивающего профиль одним `EnterpriseOKVED.is_primary`; способ обеспечения этого инварианта требует отдельного решения.
- `OKVED` имеет собственную иерархическую структуру `code`, `name_ru`, `parent_code`, `level` и не наследует `PNCBaseReference`. Префикс таблицы `pnc_` является соглашением об именовании таблиц, а не признаком принадлежности к корпоративному классификатору PNC.
- ORM-модели не содержат провайдерских сущностей или полей `api-fns.ru`. Внешний JSON должен быть нормализован до обращения к ORM, поэтому замена поставщика регистрационных сведений не требует изменения `EnterpriseProfile`, `EnterpriseOKVED` или `OKVED`.
- Целевой импорт по ИНН может сохранять подтверждённые реквизиты `EnterpriseProfile` и связи `EnterpriseOKVED`, но соответствующие нормализованная схема, сервис импорта и API endpoint в текущей реализации отсутствуют. Источник и время импорта текущей ORM-схемой также не фиксируются.
- Автоматическое сопоставление `OKVED ↔ Industry` отсутствует. Основной ОКВЭД не назначает основную отрасль PNC.
- `ProductionOrder.industry_code` описывает отрасль конечного применения или рыночный сегмент заказа, а не ОКВЭД предприятия-исполнителя. В целевой модели поле пока остаётся обязательным, однако источник его значения для входящего заказа не определён и вынесен в backlog вместе с проверкой обязательности.
- Для связи `EnterpriseProfile` ↔ `QualityCapability` используется отношение 1:1: `profile_id` имеет `unique=True`, а родительская связь — `cascade="all, delete-orphan"` и `single_parent=True`. Отдельный дублирующий `Index` не нужен.
- `Region.profiles`, `CompanySize.profiles`, `CertificateType.certificates`, `Industry.enterprise_links` и остальные обратные стороны `back_populates` присутствуют в целевой схеме; временно закомментированных отношений в приведённом целевом коде нет.
- ИНН и ОГРН хранятся как строки, поскольку это идентификаторы, а не числа для вычислений.
- Уникальность материала определяется парой `(group_code, grade_name)`. Уникальность варианта материала учитывает материал, форму, размер и единицу измерения.
- Повторно выданные сертификаты одного типа допустимы, но полный дубль по профилю, типу, дате выдачи и дате окончания запрещён.
- Наличие миграций в рабочем дереве не означает, что они проверены, закоммичены или применены к PostgreSQL. Состояние цепочки, `upgrade()`, `downgrade()` и фактической базы проверяется отдельно перед внедрением; этот документ не фиксирует все миграции как завершённые.

## Экспорт моделей

`app.models` должен экспортировать каждую реализованную модель ровно один раз.
