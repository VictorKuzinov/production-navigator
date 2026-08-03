# Модели SQLAlchemy

## Назначение документа

Документ описывает **финальную целевую архитектуру ORM-моделей** проекта
«Производственный навигатор». Приведённые ниже классы показывают итоговое
состояние модели данных после реализации всех сущностей и связей между ними.

Фактическая реализация выполняется поэтапно. Поэтому текущий код проекта на
промежуточном этапе может содержать справочник без отношений, которые уже
показаны в его финальном варианте в этом документе.

## Этапы реализации

### Этап 1. Независимые справочники PNC

Сначала создаются независимые справочники, наследующие общие поля от
`PNCBaseReference`. На этом этапе в них временно не добавляются `relationship`,
если соответствующие основные сущности ещё не реализованы.

Например, первоначальная реализация справочника типов продукции выглядит так:

```python
class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"
```

Для каждого справочника выполняется законченный цикл:

1. Создание ORM-модели.
2. Генерация миграции Alembic.
3. Проверка сгенерированной миграции.
4. Применение миграции к базе данных.
5. Проверка результата и фиксация изменений в Git.

### Этап 2. Основные сущности и связи

После создания необходимых справочников реализуются основные сущности:
`EnterpriseProfile`, `Material`, `Product`, `Equipment`, `ProductionOrder` и
другие.

На этом этапе добавляются:

- внешние ключи `ForeignKey`;
- объектные отношения `relationship`;
- двусторонняя синхронизация через `back_populates`;
- правила каскадных операций;
- ограничения уникальности и индексы.

После появления зависимой сущности соответствующий справочник приводится к
финальному виду. Например, после реализации `Product` в `ProductType`
добавляется отношение `products`, а в `Product` — обратное отношение
`type_ref` и внешний ключ на `pnc_product_type.code`.

> Важно: модели в основном блоке ниже приведены уже в финальном виде. Наличие
> `relationship` в документе не означает, что это отношение должно быть
> добавлено раньше связанной сущности в рабочем коде.

## Статус реализации справочников

| Справочник               | ORM-модель | Миграция | `relationship` | Статус                                    |
|--------------------------|:----------:|:--------:|:--------------:|-------------------------------------------|
| `TechnologyType`         |     ✅     |    ✅    |    Отложено    | Независимый справочник готов              |
| `MaterialGroup`          |     ✅     |    ✅    |    Отложено    | Связь добавляется вместе с `Material`     |
| `MaterialForm`           |     ✅     |    ✅    |    Отложено    | Связь добавляется вместе с `MaterialItem` |
| `ProductType`            |     ✅     |    ✅    |    Отложено    | Связь добавляется вместе с `Product`      |
| `EquipmentType`          |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `CraneType`              |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `TransportType`          |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `TransportScope`         |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `TransportOwnershipType` |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `WarehouseType`          |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `CertificateType`        |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `Industry`               |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `OrderType`              |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `CompanySize`            |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |
| `Region`                 |     ⏳     |    ⏳    |    Отложено    | Ожидает реализации                        |

## Финальная целевая архитектура моделей

Ниже сохранён полный исходный набор моделей. Отношения между справочниками и
основными сущностями показывают ожидаемое конечное состояние ORM-слоя.

```python
from datetime import date
from typing import List, Optional

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


# Справочники PNC

class PNCBaseReference:
    """Абстрактный набор общих полей справочников PNC."""

    __abstract__ = True

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    ics_section: Mapped[Optional[str]] = mapped_column(String(50))
    ref_system: Mapped[str] = mapped_column(String(100), nullable=False)
    ref_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    equipments: Mapped[List["Equipment"]] = relationship(back_populates="type_ref")


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"


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


class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"

    products: Mapped[List["Product"]] = relationship(back_populates="type_ref")


class CraneType(Base, PNCBaseReference):
    __tablename__ = "pnc_crane_type"

    lifting_equipments: Mapped[List["LiftingEquipment"]] = relationship(
        back_populates="type_ref"
    )


class TransportType(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_type"

    transports: Mapped[List["Transport"]] = relationship(back_populates="type_ref")


class TransportScope(Base, PNCBaseReference):
    __tablename__ = "pnc_transport_scope"

    transports: Mapped[List["Transport"]] = relationship(back_populates="scope_ref")


class TransportOwnershipType(Base, PNCBaseReference):
    """Справочник форм владения транспортом PNC"""

    __tablename__ = "pnc_transport_ownership_type"

    transports: Mapped[List["Transport"]] = relationship(back_populates="ownership_ref")


class WarehouseType(Base, PNCBaseReference):
    __tablename__ = "pnc_warehouse_type"

    warehouses: Mapped[List["Warehouse"]] = relationship(back_populates="type_ref")


class CertificateType(Base, PNCBaseReference):
    __tablename__ = "pnc_certificate_type"

    certificates: Mapped[List["EnterpriseCertificate"]] = relationship(
        back_populates="type_ref"
    )


class Industry(Base, PNCBaseReference):
    __tablename__ = "pnc_industry"

    enterprise_links: Mapped[List["EnterpriseIndustry"]] = relationship(
        back_populates="industry_ref"
    )
    orders: Mapped[List["ProductionOrder"]] = relationship(back_populates="industry_ref")


class OrderType(Base, PNCBaseReference):
    __tablename__ = "pnc_order_type"

    orders: Mapped[List["ProductionOrder"]] = relationship(back_populates="type_ref")


class CompanySize(Base, PNCBaseReference):
    __tablename__ = "pnc_company_size"

    profiles: Mapped[List["EnterpriseProfile"]] = relationship(back_populates="size_ref")


class Region(Base, PNCBaseReference):
    __tablename__ = "pnc_region"

    profiles: Mapped[List["EnterpriseProfile"]] = relationship(back_populates="region_ref")


# Профиль предприятия

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
    facilities: Mapped[List["ProductionFacility"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    warehouses: Mapped[List["Warehouse"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    lifting_equipments: Mapped[List["LiftingEquipment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    transports: Mapped[List["Transport"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    equipments: Mapped[List["Equipment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["EnterpriseCertificate"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    industries: Mapped[list["EnterpriseIndustry"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    quality_capability: Mapped[Optional["QualityCapability"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", single_parent=True
    )


class QualityCapability(Base):
    __tablename__ = "pnc_quality_capability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # unique=True уже создает уникальный индекс; отдельный Index здесь не нужен.
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"), nullable=False, unique=True
    )
    min_it_grade: Mapped[Optional[int]] = mapped_column(Integer)
    min_ra: Mapped[Optional[float]] = mapped_column(Float)
    measuring_tools: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cim_machine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="quality_capability")


class ProductionFacility(Base):
    __tablename__ = "pnc_production_facility"
    __table_args__ = (
        UniqueConstraint("profile_id", "facility_name", name="uq_facility_profile_name"),
        Index("ix_pnc_facility_profile_id", "profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
    facility_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_area: Mapped[float] = mapped_column(Float, nullable=False)
    available_area: Mapped[float] = mapped_column(Float, nullable=False)
    power_capacity: Mapped[Optional[float]] = mapped_column(Float)
    gas_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    compressed_air: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    water_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steam_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="facilities")
    equipments: Mapped[List["Equipment"]] = relationship(back_populates="facility")
    lifting_equipments: Mapped[List["LiftingEquipment"]] = relationship(
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
    warehouse_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_warehouse_type.code"), nullable=False
    )
    total_capacity_cube: Mapped[float] = mapped_column(Float, nullable=False)
    max_load_sqm: Mapped[float | None] = mapped_column(Float)
    temperature_control: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="warehouses")
    type_ref: Mapped["WarehouseType"] = relationship(back_populates="warehouses")
    lifting_equipments: Mapped[list["LiftingEquipment"]] = relationship(
        back_populates="warehouse"
    )


class LiftingEquipment(Base):
    __tablename__ = "pnc_lifting_equipment"
    __table_args__ = (
        Index("ix_pnc_lifting_profile_type", "profile_id", "crane_type_code"),
        Index("ix_pnc_lifting_facility_id", "facility_id"),
        Index("ix_pnc_lifting_warehouse_id", "warehouse_id"),
        Index("ix_pmc_lifting_load_capacity", "load_capacity_tons"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
    crane_type_code: Mapped[str] = mapped_column(ForeignKey("pnc_crane_type.code"), nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pnc_production_facility.id"))
    warehouse_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pnc_warehouse.id"))
    load_capacity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    max_lift_height: Mapped[Optional[float]] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="lifting_equipments")
    type_ref: Mapped["CraneType"] = relationship(back_populates="lifting_equipments")
    facility: Mapped[Optional["ProductionFacility"]] = relationship(
        back_populates="lifting_equipments"
    )
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        back_populates="lifting_equipments"
    )


class Transport(Base):
    __tablename__ = "pnc_transport"
    __table_args__ = (
        Index("ix_pnc_transport_profile_type", "profile_id", "transport_type_code"),
        Index("ix_pnc_transport_profile_scope", "profile_id", "transport_scope_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
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
    body_volume_cube: Mapped[Optional[float]] = mapped_column(Float)
    has_refrigeration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="transports")
    type_ref: Mapped["TransportType"] = relationship(back_populates="transports")
    scope_ref: Mapped["TransportScope"] = relationship(back_populates="transports")
    ownership_ref: Mapped["TransportOwnershipType"] = relationship(back_populates="transports")


class Equipment(Base):
    __tablename__ = "pnc_equipment"
    __table_args__ = (
        Index("ix_pnc_equipment_profile_type", "profile_id", "equipment_type_code"),
        Index("ix_pnc_equipment_facility_type", "facility_id", "equipment_type_code"),
    )

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id"),
        nullable=False,
    )
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_production_facility.id"), 
        nullable=False
    )
    equipment_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_equipment_type.code"), nullable=False
    )
    cnc: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    axes: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(
        Integer, 
        default=1, 
        nullable=False
    )
    max_diameter: Mapped[Optional[float]] = mapped_column(Float)
    working_zone_x: Mapped[Optional[float]] = mapped_column(Float)
    working_zone_y: Mapped[Optional[float]] = mapped_column(Float)
    working_zone_z: Mapped[Optional[float]] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="equipments"
    )
    facility: Mapped["ProductionFacility"] = relationship(
        back_populates="equipments"
    )
    type_ref: Mapped["EquipmentType"] = relationship(
        back_populates="equipments"
    )


class EnterpriseCertificate(Base):
    __tablename__ = "pnc_enterprise_certificate"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "certificate_type_code",
            "issue_date",
            "expiry_date",
            name="uq_certificate_profile_type_dates",
        ),
        Index(
            "ix_certificate_profile_type_expiry",
            "profile_id",
            "certificate_type_code",
            "expiry_date",
        ),
        Index("ix_certificate_expiry_date", "expiry_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pbc_enterprise_profile.id"), nullable=False)
    certificate_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_certificate_type.code"), nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="certificates")
    type_ref: Mapped["CertificateType"] = relationship(back_populates="certificates")


class EnterpriseIndustry(Base):
    __tablename__ = "pnc_enterprise_industry"
    __table_args__ = (
        UniqueConstraint("profile_id", "industry_code", name="uq_profile_industry"),
        Index("ix_enterprise_industry_industry_profile", "industry_code", "profile_id"),
        Index(
            "uq_enterprise_industry_primary",
            "profile_id",
            unique=True,
            sqlite_where=text("is_primary = 1"),
            postgresql_where=text("is_primary IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
    industry_code: Mapped[str] = mapped_column(ForeignKey("pnc_industry.code"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="industries")
    industry_ref: Mapped["Industry"] = relationship(back_populates="enterprise_links")


# Материалы и продукция

class Material(Base):
    __tablename__ = "pnc_material"
    __table_args__ = (
        UniqueConstraint("group_code", "grade_name", name="uq_pnc_material_group_grade"),
        Index("ix_pnc_material_group_code", "group_code"),
        Index("ix_pnc_material_grade_name", "grade_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_code: Mapped[str] = mapped_column(ForeignKey("pnc_material_group.code"), nullable=False)
    grade_name: Mapped[str] = mapped_column(String(100), nullable=False)
    density: Mapped[Optional[float]] = mapped_column(Float)

    group_ref: Mapped["MaterialGroup"] = relationship(back_populates="materials")
    items: Mapped[List["MaterialItem"]] = relationship(
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
    dimension_1: Mapped[Optional[float]] = mapped_column(Float)
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
    products: Mapped[List["Product"]] = relationship(
        back_populates="material_item"
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
    required_it_grade: Mapped[Optional[int]] = mapped_column(Integer)
    required_ra: Mapped[Optional[float]] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="products"
    )
    type_ref: Mapped["ProductType"] = relationship(
        back_populates="products"
    )
    material_item: Mapped["MaterialItem"] = relationship(
        back_populates="products"
    )
    orders: Mapped[list["ProductionOrder"]] = relationship(
        back_populates="product"
    )


class ProductionOrder(Base):
    __tablename__ = "pnc_production_order"
    __table_args__ = (
        UniqueConstraint("profile_id", "order_number", name="uq_order_profile_number"),
        Index("ix_order_profile_deadline", "profile_id", "deadline"),
        Index("ix_order_type_deadline", "order_type_code", "deadline"),
        Index("ix_order_industry_deadline", "industry_code", "deadline"),
        Index("ix_order_product_id", "product_id"),
        Index("ix_order_deadline", "deadline"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pnc_enterprise_profile.id"), nullable=False)
    order_type_code: Mapped[str] = mapped_column(ForeignKey("pnc_order_type.code"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("pnc_product.id"), nullable=False)
    industry_code: Mapped[str] = mapped_column(ForeignKey("pnc_industry.code"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)

    profile: Mapped["EnterpriseProfile"] = relationship(back_populates="orders")
    type_ref: Mapped["OrderType"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")
    industry_ref: Mapped["Industry"] = relationship(back_populates="orders")
```

## Примечания к ограничениям и индексам

- Первичные ключи и уникальные поля не получили дублирующих одиночных индексов.
- У `Material`- уникальна именно пара `(group_code, grade_name)`.
- Составная уникальность `MaterialItem` включает форму, размер и единицу измерения. В SQL уникальные ограничения обычно допускают несколько строк с `NULL`; если `dimension_1` должен участвовать в строгой идентичности записи, его следует сделать обязательным либо нормализовать размеры в отдельную сущность.
- Для `EnterpriseCertificate` разрешено хранить повторно выданные сертификаты одного типа, но запрещены полные дубли по профилю, типу и срокам действия.
- Частичный уникальный индекс `uq_enterprise_industry_primary` допускает не более одной основной отрасли на профиль в SQLite и PostgreSQL.
- Индексы выбраны под основные сценарии фильтрации: профиль, площадка, тип справочника, отрасль, регион и срок исполнения.
