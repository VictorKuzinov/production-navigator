```text
app/models/
├── __init__.py
├── base_reference.py
├── pnc_reference.py
├── enterprises.py
├── productions.py
├── materials.py
├── equipments.py
├── products.py
└── orders.py
```

# base_reference.py
- Только общий абстрактный класс:
PNCBaseReference
Он содержит общие поля всех справочников:
```text
    code
    name_ru
    ics_section
    ref_system
    ref_code
    description
```

# equipment.py

- Справочник оборудования и само оборудование:
EquipmentType
Equipment
```python
    class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="type_ref"
    )


class Equipment(Base):
    __tablename__ = "equipment"

    # поля Equipment
```

# materials.py
```text
MaterialGroup
MaterialForm
Material
MaterialItem
```
```python
class MaterialGroup(Base, PNCBaseReference):
    __tablename__ = "pnc_material_group"


class MaterialForm(Base, PNCBaseReference):
    __tablename__ = "pnc_material_form"


class Material(Base):
    __tablename__ = "material"


class MaterialItem(Base):
    __tablename__ = "material_item"
```
# products.py

```text
ProductType
Product
```
```python
class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"


class Product(Base):
    __tablename__ = "product"
```

# orders.py
```text
OrderType
ProductionOrder
```
```python
class OrderType(Base, PNCBaseReference):
    __tablename__ = "pnc_order
```

```python
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.enterprise import EnterpriseProfile
    from app.models.production import ProductionFacility


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"

    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="type_ref"
    )


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        Index(
            "ix_equipment_profile_type",
            "profile_id",
            "equipment_type_code",
        ),
        Index(
            "ix_equipment_facility_type",
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
        ForeignKey("enterprise_profile.id"),
        nullable=False,
    )

    facility_id: Mapped[int] = mapped_column(
        ForeignKey("production_facility.id"),
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
        back_populates="equipments"
    )

    facility: Mapped["ProductionFacility"] = relationship(
        back_populates="equipments"
    )

    type_ref: Mapped["EquipmentType"] = relationship(
        back_populates="equipments"
    )
```

# pnc_reference.py
```python
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"
```
