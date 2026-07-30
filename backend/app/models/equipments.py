
# Сторонние пакеты
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Локальные
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class EquipmentType(Base, PNCBaseReference):
    __tablename__ = "pnc_equipment_type"
