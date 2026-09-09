"""Intermediate DTOs produced by HTML parsing.

These are intentionally plain dataclasses — they carry the raw extracted
data before any projection into PreparedOpportunityInput.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ParsedEisPosition:
    """Single purchase position (лоток / позиция закупки)."""

    okpd2_code: str | None = None
    name: str = ""
    unit: str | None = None
    unit_price: Decimal | None = None
    quantity: Decimal | None = None


@dataclass(frozen=True)
class ParsedEisNotice:
    """All data extracted from a public ЕИС 44-ФЗ notice page."""

    procurement_number: str = ""
    title: str = ""
    law: str = "44-ФЗ"
    procurement_method: str | None = None
    status_text: str | None = None
    customer: str | None = None
    platform_name: str | None = None
    platform_url: str | None = None
    region: str | None = None
    application_start: datetime | None = None
    application_deadline: datetime | None = None
    results_date: datetime | None = None
    max_price: Decimal | None = None
    currency: str | None = None
    execution_deadline_text: str | None = None
    delivery_location: str | None = None
    okpd2_codes: list[str] = field(default_factory=list)
    positions: list[ParsedEisPosition] = field(default_factory=list)
    quality_warranty: str | None = None
    source_url: str | None = None
