
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class MaterialGroup(Base, PNCBaseReference):
    __tablename__ = "pnc_material_group"


class MaterialForm(Base, PNCBaseReference):
    __tablename__ = "pnc_material_form"

