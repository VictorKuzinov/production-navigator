# Схема организации моделей базы данных

## 1. Назначение документа

Документ определяет:

- структуру пакета `app.models`;
- распределение ORM-моделей по файлам;
- порядок поэтапной реализации моделей и связей;
- правила регистрации моделей в SQLAlchemy и Alembic.

Подробный состав полей, ограничений и индексов каждой сущности описывается в `08_sqlalchemy_models.md`. Здесь фиксируются структура модулей и зависимости между группами моделей.

## 2. Структура пакета моделей

Файлы предметных областей называются во множественном числе, поскольку каждый из них содержит несколько связанных моделей.

```text
app/models/
├── __init__.py
├── base_reference.py
├── pnc_reference.py
├── okved.py
├── enterprises.py
├── productions.py
├── materials.py
├── equipments.py
├── products.py
└── orders.py
```

Соглашение об именовании:

- `equipments.py`, а не `equipment.py`;
- `enterprises.py`, а не `enterprise.py`;
- `productions.py`, а не `production.py`;
- `materials.py`, `products.py` и `orders.py` также используются во множественном числе;
- имена ORM-классов остаются в единственном числе: `Equipment`, `Product`, `ProductionOrder`.

## 3. Рекомендуемый workflow реализации новых моделей

Ниже описан общий поэтапный шаблон для разработки новой группы моделей, а не
текущий статус уже описанных сущностей. Фактический состав целевой ORM
определяется `08_sqlalchemy_models.md`, а наличие конкретных классов в рабочем
дереве проверяется по `backend/app/models/`.

При постепенной реализации окончательные двусторонние связи не требуется
добавлять до появления обеих зависимых сущностей.

### 3.1. Первый шаг — независимые справочники

Сначала создаются таблицы справочников PNC без `relationship()`:

```python
class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"
```

Такой промежуточный вариант корректен. Он позволяет:

1. создать независимую модель;
2. сгенерировать миграцию Alembic;
3. проверить миграцию;
4. применить её к базе данных;
5. зафиксировать законченный шаг отдельным коммитом.

### 3.2. Следующий шаг — зависимые сущности

После появления основной сущности добавляются внешний ключ и обе стороны ORM-связи.

```python
class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"

    products: Mapped[list["Product"]] = relationship(
        back_populates="type_ref",
    )


class Product(Base):
    __tablename__ = "pnc_product"

    product_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_product_type.code"),
        nullable=False,
    )

    type_ref: Mapped["ProductType"] = relationship(
        back_populates="products",
    )
```

`ForeignKey` создаёт связь на уровне базы данных. `relationship()` и `back_populates` обеспечивают двусторонний объектный доступ в SQLAlchemy.

### 3.3. Правило добавления связей

- справочник можно мигрировать без зависимой сущности;
- `relationship()` добавляется после реализации зависимой сущности;
- имена в `back_populates` должны совпадать с именами полей на противоположной стороне;
- новая миграция должна содержать только ожидаемые изменения;
- перед `alembic upgrade head` сгенерированная миграция проверяется вручную.

## 4. Распределение моделей по файлам

### 4.1. `base_reference.py`

Содержит общий абстрактный класс для корпоративных справочников PNC:

```text
PNCBaseReference
├── code
├── name_ru
├── ics_section
├── ref_system
├── ref_code
└── description
```

Пример:

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class PNCBaseReference:
    """Общие поля справочников PNC."""

    __abstract__ = True

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    ics_section: Mapped[str | None] = mapped_column(String(50))
    ref_system: Mapped[str] = mapped_column(String(100), nullable=False)
    ref_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
```

`PNCBaseReference` не создаёт отдельную таблицу. Его поля наследуются конкретными справочниками.

Смысл полей един для всех корпоративных справочников PNC:

- `code` — стабильный внутренний бизнес-идентификатор Production Navigator;
- `name_ru` — русское отображаемое название;
- `ics_section` — соответствующий раздел ISO ICS, когда применимо;
- `ref_system` — внешняя классификационная или нормативная система;
- `ref_code` — идентификатор значения во внешней системе;
- `description` — содержательное описание значения и области применения.

`code` и `ref_code` не взаимозаменяемы. Например, внутренний `PNC_REG_66` может быть сопоставлен с `ISO 3166-2 / RU-SVE`. Внешний классификатор `OKVED` имеет другую структуру и не наследует `PNCBaseReference`.

### 4.2. `pnc_reference.py`

Содержит самостоятельные PNC-справочники, которые по целевому распределению не
относятся к специализированному доменному модулю:

```text
TechnologyType
```

```python
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"
```

### 4.3. `enterprises.py`

Содержит справочники и сущности производственного профиля:

```text
CertificateType
Industry
CompanySize
Region
EnterpriseProfile
EnterpriseCertificate
EnterpriseIndustry
EnterpriseOKVED
QualityCapability
```
```text
EnterpriseProfile
        │
        └─────── 1 : 1 ───────► QualityCapability
                                  │
                                  ├── min_it_grade
                                  ├── min_ra
                                  ├── measuring_tools
                                  ├── cim_machine
                                  └── notes
```

`EnterpriseIndustry` связывает профиль с обслуживаемыми отраслевыми рынками PNC. `EnterpriseOKVED` связывает тот же профиль с официально зарегистрированными видами деятельности. Их признаки `is_primary` имеют разный смысл и не являются дублями.

### 4.4. `okved.py`

Содержит локальное иерархическое представление внешнего классификатора ОКВЭД:

```text
OKVED
├── code
├── name_ru
├── parent_code
└── level
```

```text
EnterpriseProfile 1 ─── N EnterpriseOKVED N ─── 1 OKVED
OKVED             1 ─── N OKVED.children
```

Модель `OKVED` хранится в `okved.py`; связующая модель `EnterpriseOKVED` относится к профилю предприятия и находится в `enterprises.py`. `EnterpriseOKVED` не дублирует `name_ru`: название получается через отношение к `OKVED`.

ORM-схема не зависит от провайдера регистрационных сведений: таблицы или поля с
контрактом `api-fns.ru` в доменную БД не добавляются. Нормализация внешнего JSON
и правила импорта относятся к интеграционному и прикладному слоям. После
подтверждения пользователя они могут изменять только согласованные реквизиты
`EnterpriseProfile` и связи `EnterpriseOKVED`; `EnterpriseIndustry` и сущности
производственного профиля из такого ответа не создаются. Отдельная схема аудита
источника и времени импорта пока не спроектирована.

### 4.5. `productions.py`

Содержит модели производственной и логистической инфраструктуры:

```text
CraneType
TransportType
TransportScope
TransportOwnershipType
WarehouseType
ProductionFacility
Warehouse
LiftingEquipment
Transport
```

### 4.6. `materials.py`

Содержит справочники и сущности материалов:

```text
MaterialGroup
MaterialForm
Material
MaterialItem
```

При разработке новой группы моделей справочники могут сначала реализовываться
независимо:

```python
class MaterialGroup(Base, PNCBaseReference):
    __tablename__ = "pnc_material_group"


class MaterialForm(Base, PNCBaseReference):
    __tablename__ = "pnc_material_form"
```

Затем к ним могут быть добавлены `Material` и `MaterialItem`, внешние ключи и
`relationship()`. Это пример порядка реализации, а не описание текущего статуса:
в целевую ORM из `08_sqlalchemy_models.md` входят все четыре модели.

### 4.7. `equipments.py`

Содержит:

```text
EquipmentType
Equipment
```

Пример первоначальной независимой модели справочника в таком workflow:

```python
class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"
```

В рамках поэтапного шаблона после появления `EnterpriseProfile`,
`ProductionFacility` и `Equipment` справочник получает обратную связь:

```python
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseProfile
    from app.models.productions import ProductionFacility


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="type_ref",
    )


class Equipment(Base):
    __tablename__ = "pnc_equipment"
    __table_args__ = (
        Index(
            "ix_pnc_equipment_profile_type",
            "profile_id",
            "equipment_type_code",
        ),
        Index(
            "ix_pnc_equipment_facility_type",
            "facility_id",
            "equipment_type_code",
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
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_production_facility.id"),
        nullable=False,
    )
    equipment_type_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_equipment_type.code"),
        nullable=False,
    )
    cnc: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    axes: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    max_diameter: Mapped[float | None] = mapped_column(Float)
    working_zone_x: Mapped[float | None] = mapped_column(Float)
    working_zone_y: Mapped[float | None] = mapped_column(Float)
    working_zone_z: Mapped[float | None] = mapped_column(Float)

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="equipments",
    )
    facility: Mapped["ProductionFacility"] = relationship(
        back_populates="equipments",
    )
    type_ref: Mapped["EquipmentType"] = relationship(
        back_populates="equipments",
    )
```

Импорты для проверки типов используют актуальные множественные имена модулей:

```python
from app.models.enterprises import EnterpriseProfile
from app.models.productions import ProductionFacility
```

### 4.8. `products.py`

Содержит:

```text
ProductType
Product
```

При поэтапной реализации сначала может быть создан `ProductType`, а после
появления `Product` — добавлены внешний ключ и двусторонняя связь. В целевой ORM
обе модели уже входят в одну согласованную структуру.

### 4.9. `orders.py`

Содержит:

```text
OrderType
ProductionOrder
```

При поэтапной реализации сначала может быть создан `OrderType`, а связь
`OrderType.orders` — после появления `ProductionOrder`. В целевой ORM обе модели
уже входят в одну согласованную структуру.

## 5. Регистрация моделей

Alembic работает с `Base.metadata`, но видит только те модели, модули которых были импортированы.

`app/models/__init__.py` должен экспортировать каждую фактически присутствующую
модель ровно один раз. Ниже приведён полный снимок наблюдаемого экспорта в
рабочем дереве на 2026-08-14, а не сокращённый концептуальный фрагмент:

```python
from app.models.enterprises import (
    CertificateType,
    CompanySize,
    EnterpriseCertificate,
    EnterpriseIndustry,
    EnterpriseOKVED,
    EnterpriseProfile,
    Industry,
    QualityCapability,
    Region,
)
from app.models.equipments import Equipment, EquipmentType
from app.models.materials import (
    Material,
    MaterialForm,
    MaterialGroup,
    MaterialItem,
)
from app.models.okved import OKVED
from app.models.orders import OrderType, ProductionOrder
from app.models.pnc_reference import TechnologyType
from app.models.productions import (
    CraneType,
    LiftingEquipment,
    ProductionFacility,
    Transport,
    TransportOwnershipType,
    TransportScope,
    TransportType,
    Warehouse,
    WarehouseType,
)
from app.models.products import Product, ProductType

__all__ = [
    "TechnologyType",
    "MaterialGroup",
    "MaterialForm",
    "Material",
    "MaterialItem",
    "ProductType",
    "Product",
    "OrderType",
    "ProductionOrder",
    "EquipmentType",
    "Equipment",
    "CertificateType",
    "Industry",
    "CompanySize",
    "Region",
    "EnterpriseProfile",
    "EnterpriseCertificate",
    "EnterpriseIndustry",
    "QualityCapability",
    "CraneType",
    "TransportType",
    "TransportScope",
    "TransportOwnershipType",
    "WarehouseType",
    "ProductionFacility",
    "Warehouse",
    "LiftingEquipment",
    "Transport",
    "OKVED",
    "EnterpriseOKVED",
]
```

При появлении новых моделей экспорт обновляется вместе с их фактической
реализацией. Черновые или отсутствующие зависимые модели импортировать не
следует. Наличие имени в этом снимке не доказывает, что соответствующая миграция
применена к конкретной базе данных.

В `alembic/env.py` пакет моделей импортируется до использования метаданных:

```python
import app.models  # noqa: F401

from app.db.database import Base

target_metadata = Base.metadata
```

## 6. Рабочий цикл миграции

Для каждого небольшого законченного изменения используется один цикл:

```text
Модель
  ↓
Регистрация в app/models/__init__.py
  ↓
alembic revision --autogenerate
  ↓
Проверка upgrade(), downgrade() и down_revision
  ↓
alembic upgrade head
  ↓
alembic current
  ↓
Commit
```

Пример команд:

```powershell
alembic revision --autogenerate -m "create product type reference"
alembic upgrade head
alembic current
git add app/models alembic/versions
git commit -m "Add ProductType reference model and migration"
```

Для новой группы моделей допустима отдельная миграция для каждого справочника.
Это общий рекомендуемый приём, который упрощает проверку, откат и поиск ошибок;
он не описывает текущий статус существующих миграций.

## 7. Итоговые правила

- файлы предметных областей именуются во множественном числе;
- ORM-классы именуются в единственном числе;
- справочники PNC наследуют общие поля от `PNCBaseReference`;
- `OKVED` является отдельным внешним иерархическим классификатором и не наследует `PNCBaseReference`;
- `EnterpriseOKVED` и `EnterpriseIndustry` описывают соответственно регистрационный и рыночный контекст профиля;
- основной `OKVED` не преобразуется в основную `Industry` автоматически;
- сначала создаются независимые справочники без `relationship()`;
- связи добавляются после появления зависимых сущностей;
- незавершённые модели не регистрируются в `app.models`;
- каждая автосгенерированная миграция проверяется до применения;
- структура базы изменяется только через Alembic, а не вручную через pgAdmin.
