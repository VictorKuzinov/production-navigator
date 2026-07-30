# productions.py
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class CraneType(Base, PNCBaseReference):
    __tablename__ = "pnc_crane_type"