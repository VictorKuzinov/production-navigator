from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from app.db.database import Base
from app.models.base_reference import PNCBaseReference

if TYPE_CHECKING:
    from app.models.profile_capabilities import ProfileTechnologyCapability


class TechnologyType(Base, PNCBaseReference):
    __tablename__ = "pnc_technology_type"

    profile_capabilities: Mapped[list["ProfileTechnologyCapability"]] = relationship(
        back_populates="technology",
        passive_deletes=True,
    )
