
# Сторонние пакеты
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class PNCBaseReference:
    """Общие поля справочников PNC."""

    __abstract__ = True

    code: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    name_ru: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ics_section: Mapped[str | None] = mapped_column(String(50))

    ref_system: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    ref_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)