from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"


