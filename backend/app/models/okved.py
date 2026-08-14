from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseOKVED


class OKVED(Base):
    __tablename__ = "pnc_okved"

    __table_args__ = (
        Index(
            "ix_pnc_okved_parent_code",
            "parent_code",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
    )

    name_ru: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    parent_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_okved.code"),
        nullable=True,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    children: Mapped[list["OKVED"]] = relationship(
        back_populates="parent",
    )

    parent: Mapped["OKVED | None"] = relationship(
        back_populates="children",
        remote_side=[code],
    )

    enterprises: Mapped[list["EnterpriseOKVED"]] = relationship(
        back_populates="okved",
    )