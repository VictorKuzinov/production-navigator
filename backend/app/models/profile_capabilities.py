from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.enterprises import EnterpriseProfile
    from app.models.materials import Material, MaterialGroup
    from app.models.pnc_reference import TechnologyType


# ---------------------------------------------------------------------------
# Confirmer whitespace — canonical Python str.isspace() codepoint set.
# Verified: ``chr(cp).isspace() is True`` for every codepoint in this tuple
# and no other codepoints below U+FFFF in the current CPython runtime.
# ---------------------------------------------------------------------------
CONFIRMER_WHITESPACE_CODEPOINTS: tuple[int, ...] = (
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D,  # TAB, LF, VT, FF, CR
    0x001C, 0x001D, 0x001E, 0x001F,           # file/group/record/unit sep
    0x0020,                                     # space
    0x0085,                                     # next line (NEL)
    0x00A0,                                     # non-breaking space
    0x1680,                                     # ogham space mark
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004,   # en/ogham/em/thin/hair
    0x2005, 0x2006, 0x2007, 0x2008, 0x2009,   # thick/punc/3em/em/hair
    0x200A,                                     # thin space
    0x2028, 0x2029,                             # line/paragraph separator
    0x202F,                                     # narrow no-break space
    0x205F,                                     # medium mathematical space
    0x3000,                                     # ideographic space
)


def confirmer_whitespace_chars() -> str:
    """Join all canonical whitespace codepoints into a single Python string."""
    return "".join(chr(cp) for cp in CONFIRMER_WHITESPACE_CODEPOINTS)


def sqlite_whitespace_literal() -> str:
    """Single-quoted SQL literal embedding physical whitespace characters.

    Valid for SQLite execution (used by ORM model for async test tables).
    """
    return "'" + confirmer_whitespace_chars() + "'"


def postgres_whitespace_literal() -> str:
    """U&-escaped PostgreSQL string literal — pure ASCII hex escapes.

    Valid for PostgreSQL execution.  No physical control or newline characters
    appear inside the literal.
    """
    escapes = "".join(f"\\{cp:04X}" for cp in CONFIRMER_WHITESPACE_CODEPOINTS)
    return f"U&'{escapes}'"


# ORM CheckConstraint uses the SQLite-valid physical literal.
_whitespace_literal = sqlite_whitespace_literal()


class CapabilityState(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ProfileSectionCode(StrEnum):
    TECHNOLOGIES = "TECHNOLOGIES"
    MATERIALS = "MATERIALS"


class ProfileSectionState(StrEnum):
    CONFIRMED_COMPLETE = "CONFIRMED_COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ProfileTechnologyCapability(Base):
    __tablename__ = "pnc_profile_technology_capability"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "technology_code",
            name="uq_pnc_profile_technology_capability_identity",
        ),
        CheckConstraint(
            "state IN ('SUPPORTED', 'UNSUPPORTED', 'UNKNOWN')",
            name="ck_pnc_profile_technology_capability_state",
        ),
        Index(
            "ix_pnc_profile_technology_capability_technology_code",
            "technology_code",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    technology_code: Mapped[str] = mapped_column(
        ForeignKey("pnc_technology_type.code", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[CapabilityState] = mapped_column(
        String(20),
        nullable=False,
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="technology_capabilities",
    )
    technology: Mapped["TechnologyType"] = relationship(
        back_populates="profile_capabilities",
    )


class ProfileMaterialCapability(Base):
    __tablename__ = "pnc_profile_material_capability"
    __table_args__ = (
        CheckConstraint(
            "((material_group_code IS NOT NULL AND material_id IS NULL) OR "
            "(material_group_code IS NULL AND material_id IS NOT NULL))",
            name="ck_pnc_profile_material_capability_exactly_one_target",
        ),
        CheckConstraint(
            "state IN ('SUPPORTED', 'UNSUPPORTED', 'UNKNOWN')",
            name="ck_pnc_profile_material_capability_state",
        ),
        UniqueConstraint(
            "profile_id",
            "material_group_code",
            name="uq_pnc_profile_material_capability_group_identity",
        ),
        UniqueConstraint(
            "profile_id",
            "material_id",
            name="uq_pnc_profile_material_capability_material_identity",
        ),
        Index(
            "ix_pnc_profile_material_capability_group_code",
            "material_group_code",
        ),
        Index(
            "ix_pnc_profile_material_capability_material_id",
            "material_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_group_code: Mapped[str | None] = mapped_column(
        ForeignKey("pnc_material_group.code", ondelete="RESTRICT"),
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("pnc_material.id", ondelete="RESTRICT"),
    )
    state: Mapped[CapabilityState] = mapped_column(
        String(20),
        nullable=False,
    )

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="material_capabilities",
    )
    material_group: Mapped["MaterialGroup | None"] = relationship(
        back_populates="profile_capabilities",
        foreign_keys=[material_group_code],
    )
    material: Mapped["Material | None"] = relationship(
        back_populates="profile_capabilities",
        foreign_keys=[material_id],
    )


class ProfileSectionCompleteness(Base):
    __tablename__ = "pnc_profile_section_completeness"
    __table_args__ = (
        CheckConstraint(
            "section_code IN ('TECHNOLOGIES', 'MATERIALS')",
            name="ck_pnc_profile_section_completeness_section_code",
        ),
        CheckConstraint(
            "state IN ('CONFIRMED_COMPLETE', 'PARTIAL', 'UNKNOWN')",
            name="ck_pnc_profile_section_completeness_state",
        ),
        CheckConstraint(
            "((state = 'CONFIRMED_COMPLETE' "
            "AND confirmed_at IS NOT NULL "
            "AND confirmed_by IS NOT NULL "
            "AND length(trim(confirmed_by, "
            f"{_whitespace_literal})) "
            "BETWEEN 1 AND 128) "
            "OR (state IN ('PARTIAL', 'UNKNOWN') "
            "AND confirmed_at IS NULL "
            "AND confirmed_by IS NULL))",
            name="ck_pnc_profile_section_completeness_confirmation",
        ),
    )

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("pnc_enterprise_profile.id", ondelete="CASCADE"),
        primary_key=True,
    )
    section_code: Mapped[ProfileSectionCode] = mapped_column(
        String(20),
        primary_key=True,
    )
    state: Mapped[ProfileSectionState] = mapped_column(
        String(20),
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(128))

    profile: Mapped["EnterpriseProfile"] = relationship(
        back_populates="capability_sections",
    )
