"""Project ParsedEisNotice into PreparedOpportunityInput.

This is the deterministic bridge between raw ЕИС data and the existing
ProcurementOpportunity ingestion contract.

Technology / material mapping rules:
- ONLY map terms that have an unambiguous match in the existing
  reference layer.
- Unknown terms are left as unresolved evidence.
- Never turn the mere presence of a substring into a confirmed
  MANDATORY requirement unless the phrase is an unambiguous operation
  descriptor ("токарные работы", "фрезерные работы", "шлифовка",
  "плазменная резка", "лазерная резка", "газовая резка").
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.procurement_opportunities import (
    ProcurementOpportunityStatus,
    RequirementStrength,
)
from app.schemas.procurement_opportunities import (
    MaterialRequirementInput,
    PreparedOpportunityInput,
    TechnologyRequirementInput,
)
from app.sources.eis_public.dto import ParsedEisNotice

SOURCE_CODE = "eis_public_44fz"

# ЕИС publishes national (Russia) times — Moscow timezone (UTC+3).
_EIS_TZ = timezone(timedelta(hours=3))

# ---------------------------------------------------------------------------
# ЕИС status → ProcurementOpportunityStatus mapping
# ---------------------------------------------------------------------------
# Terminal states have precedence over OPEN wording.  The mapping is
# iterated in a specific order: OPEN patterns are the least specific, so
# they are checked LAST.  If a substring like "подача заявок" appears in
# a terminal phrase ("Подача заявок завершена"), the terminal pattern
# must win.
_OPEN_PATTERNS: list[str] = [
    "прием заявок",
    "идет прием",
    "приём заявок",
    "заявки принимаются",
]

# "подача заявок" alone → OPEN; if followed by a terminal word it is
# matched by the terminal logic and must NOT be reported as OPEN.
_OPEN_EXACT_PATTERNS: list[str] = [
    "подача заявок",
]

_TERMINAL_PATTERNS: list[tuple[str, ProcurementOpportunityStatus]] = [
    ("завершена", ProcurementOpportunityStatus.CLOSED),
    ("завершено", ProcurementOpportunityStatus.CLOSED),
    ("оценка завершена", ProcurementOpportunityStatus.CLOSED),
    ("определение поставщика завершено", ProcurementOpportunityStatus.CLOSED),
    ("закрыта", ProcurementOpportunityStatus.CLOSED),
    ("отменена", ProcurementOpportunityStatus.CANCELLED),
    ("отменено", ProcurementOpportunityStatus.CANCELLED),
    ("отклонена", ProcurementOpportunityStatus.CANCELLED),
    ("признана несостоявшейся", ProcurementOpportunityStatus.CANCELLED),
    ("контракт заключён", ProcurementOpportunityStatus.AWARDED),
    ("контракт заключен", ProcurementOpportunityStatus.AWARDED),
]


def _map_status(status_text: str | None) -> ProcurementOpportunityStatus:
    if not status_text:
        return ProcurementOpportunityStatus.UNKNOWN
    lower = status_text.lower()

    # 1. Terminal states first — they have highest precedence.
    for pattern, status in _TERMINAL_PATTERNS:
        if pattern in lower:
            return status

    # 2. Exact OPEN phrases.
    for pattern in _OPEN_EXACT_PATTERNS:
        if pattern in lower:
            # If the phrase is "подача заявок завершена" the terminal
            # branch above already returned CLOSED.  Reaching here means
            # a pure OPEN phrase.
            return ProcurementOpportunityStatus.OPEN

    # 3. Other OPEN phrases.
    for pattern in _OPEN_PATTERNS:
        if pattern in lower:
            return ProcurementOpportunityStatus.OPEN

    # Nothing recognisable → UNKNOWN is safer than OPEN.
    return ProcurementOpportunityStatus.UNKNOWN


# ---------------------------------------------------------------------------
# ЕИС procurement method → procurement_type code
# ---------------------------------------------------------------------------
_METHOD_MAP: dict[str, str] = {
    "запрос котировок в электронной форме": "ELECTRONIC_QUOTE_REQUEST",
    "запрос котировок": "QUOTE_REQUEST",
    "электронный аукцион": "ELECTRONIC_AUCTION",
    "открытый конкурс": "OPEN_TENDER",
    "закрытый конкурс": "CLOSED_TENDER",
    "запрос предложений": "PROPOSAL_REQUEST",
    "единственный поставщик": "SOLE_SUPPLIER",
    "конкурентный диалог": "COMPETITIVE_DIALOG",
}


def _map_method(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower().strip()
    for pattern, code in _METHOD_MAP.items():
        if pattern in lower:
            return code
    return None


# ---------------------------------------------------------------------------
# Region name → PNC region code
# ---------------------------------------------------------------------------
_REGION_MAP: dict[str, str] = {
    "москва": "PNC_REG_77",
    "московская область": "PNC_REG_50",
    "санкт-петербург": "PNC_REG_78",
    "свердловская область": "PNC_REG_66",
    "челябинская область": "PNC_REG_74",
    "нижегородская область": "PNC_REG_52",
    "самарская область": "PNC_REG_63",
    "краснодарский край": "PNC_REG_23",
    "республика татарстан": "PNC_REG_16",
    "республика башкортостан": "PNC_REG_02",
    "новосибирская область": "PNC_REG_54",
    "ростовская область": "PNC_REG_61",
    "волгоградская область": "PNC_REG_34",
    "вологодская область": "PNC_REG_35",
    "воронежская область": "PNC_REG_36",
    "омская область": "PNC_REG_55",
    "оренбургская область": "PNC_REG_56",
    "пензенская область": "PNC_REG_58",
    "пермский край": "PNC_REG_59",
    "красноярский край": "PNC_REG_24",
    "тюменская область": "PNC_REG_72",
    "тульская область": "PNC_REG_71",
    "рызанская область": "PNC_REG_62",
    "саратовская область": "PNC_REG_64",
    "иркутская область": "PNC_REG_38",
    "камчатский край": "PNC_REG_41",
    "кемеровская область": "PNC_REG_42",
    "кировская область": "PNC_REG_43",
    "костромская область": "PNC_REG_44",
    "курганская область": "PNC_REG_45",
    "Курская область": "PNC_REG_46",
    "ленинградская область": "PNC_REG_47",
    "липецкая область": "PNC_REG_48",
    "магаданская область": "PNC_REG_49",
    "мурманская область": "PNC_REG_51",
    "новгородская область": "PNC_REG_53",
    "псковская область": "PNC_REG_60",
    "алтайский край": "PNC_REG_22",
    "приморский край": "PNC_REG_25",
    "ставропольский край": "PNC_REG_26",
    "хабаровский край": "PNC_REG_27",
    "амурская область": "PNC_REG_28",
    "архангельская область": "PNC_REG_29",
    "астраханская область": "PNC_REG_30",
    "белгородская область": "PNC_REG_31",
    "брянская область": "PNC_REG_32",
    "владимирская область": "PNC_REG_33",
    "ивановская область": "PNC_REG_37",
    "калининградская область": "PNC_REG_39",
    "калужская область": "PNC_REG_40",
    "смоленская область": "PNC_REG_67",
    "тамбовская область": "PNC_REG_68",
    "тверская область": "PNC_REG_69",
    "томская область": "PNC_REG_70",
    "ульяновская область": "PNC_REG_73",
    "ярославская область": "PNC_REG_76",
    "забайкальский край": "PNC_REG_75",
}


def _map_region(region_text: str | None) -> str | None:
    if not region_text:
        return None
    lower = region_text.lower().strip()
    for name, code in _REGION_MAP.items():
        if name in lower:
            return code
    return None


# ---------------------------------------------------------------------------
# Deterministic technology mapping from position names
# ---------------------------------------------------------------------------
# Very conservative patterns — only unambiguous *operation* phrases.
# The mere presence of a substring ("сверл" inside "Поставка сверл" or
# "токарн" inside "Поставка токарных станков") must NOT yield a
# requirement: a purchase position describing a *deliverable asset* is
# not evidence of a *manufacturing operation*.
# Each pattern is an explicit operation descriptor.
_TECH_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    # Turning work
    (re.compile(r"токарн\w*\s+работ\w*", re.I), "MACHINING"),
    (re.compile(r"токарн\w*\s+обработк\w*", re.I), "MACHINING"),
    # Milling work
    (re.compile(r"фрезерн\w*\s+работ\w*", re.I), "MACHINING"),
    (re.compile(r"фрезерн\w*\s+обработк\w*", re.I), "MACHINING"),
    # Grinding work
    (re.compile(r"шлифов\w*\s+работ\w*", re.I), "MACHINING"),
    (re.compile(r"шлифов\w*\s+обработк\w*", re.I), "MACHINING"),
    # Drilling work — explicit operation only ("сверлильные работы").
    # "Поставка сверл" (deliverable drill bits) must NOT match.
    (re.compile(r"сверлильн\w*\s+работ\w*", re.I), "MACHINING"),
    (re.compile(r"сверлен\w*\s+работ\w*", re.I), "MACHINING"),
    # Thermal cutting (explicit phrases only)
    (re.compile(r"плазменн\w*\s+резк\w*", re.I), "PREPARATORY"),
    (re.compile(r"лазерн\w*\s+резк\w*", re.I), "PREPARATORY"),
    (re.compile(r"газов\w*\s+резк\w*", re.I), "PREPARATORY"),
]


def _collect_technologies(
    positions_text: list[str],
) -> list[TechnologyRequirementInput]:
    """Deterministically map position texts to technology requirements.

    Only exact operation-phrase matches are accepted.  Each
    technology_code appears at most once in the result.
    """
    seen: set[str] = set()
    result: list[TechnologyRequirementInput] = []

    for text in positions_text:
        for pattern, code in _TECH_KEYWORDS:
            if code not in seen and pattern.search(text):
                seen.add(code)
                result.append(
                    TechnologyRequirementInput(
                        technology_code=code,
                        requirement_strength=RequirementStrength.MANDATORY,
                    )
                )

    return result or None


# ---------------------------------------------------------------------------
# Material mapping from position texts
# ---------------------------------------------------------------------------
# Material keywords are intentionally conservative.
# "низколегированная сталь" / "нелегированная сталь" are NOT treated as
# STEEL_ALLOY: the "легированн" root is embedded in a longer word there,
# and the `(?<!\S)` guard rejects any match that is not a standalone word
# (preceded by whitespace / start of string).
_MATERIAL_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"конструкционн\w*\s+стал", re.I),
        "STEEL_CARBON",
    ),
    (
        re.compile(r"нержаве\w*\s+стал", re.I),
        "STEEL_STAINLESS",
    ),
    (
        re.compile(r"(?<!\S)легированн\w*\s+стал", re.I),
        "STEEL_ALLOY",
    ),
]

# Material-category *mentions* used only to detect an ambiguous mixture
# in a single position line.  This is a conservative guard, NOT a new
# mapping layer and NOT a new reference dictionary.
_MATERIAL_MENTION_RE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"нержаве\w*", re.I), "stainless"),
    (re.compile(r"(?<!\S)легирован\w*", re.I), "alloy"),
    (re.compile(r"конструкционн\w*", re.I), "carbon"),
    (re.compile(r"углеродист\w*", re.I), "carbon"),
    (re.compile(r"жаропрочн\w*", re.I), "heat_resistant"),
    (re.compile(r"цветн\w*", re.I), "non_ferrous"),
]


def _is_ambiguous_material_mixture(text: str) -> bool:
    """Return True if one text line mentions several material categories.

    A line such as "легированным сталям (нержавеющая сталь, жаропрочная
    сталь)" or "по нержавеющей, цветным и легированным сталям" lists
    multiple materials and must NOT be turned into several independent
    MANDATORY requirements.
    """
    categories: set[str] = set()
    for pattern, tag in _MATERIAL_MENTION_RE:
        if pattern.search(text):
            categories.add(tag)
    return len(categories) >= 2


def _collect_materials(
    positions_text: list[str],
) -> list[MaterialRequirementInput] | None:
    """Deterministically map position texts to material requirements.

    Conservative semantics: a single position line that is an ambiguous
    material mixture is left unresolved.  Returns a list of
    MaterialRequirementInput or None.
    """
    seen: set[str] = set()
    result: list[MaterialRequirementInput] = []

    for text in positions_text:
        if _is_ambiguous_material_mixture(text):
            continue

        for pattern, code in _MATERIAL_KEYWORDS:
            if code not in seen and pattern.search(text):
                seen.add(code)
                result.append(
                    MaterialRequirementInput(
                        material_group_code=code,
                        requirement_strength=RequirementStrength.MANDATORY,
                    )
                )

    return result or None


# ---------------------------------------------------------------------------
# Main projector
# ---------------------------------------------------------------------------


def _money_decimal(value: Decimal | None) -> str | None:
    """Serialise a money Decimal for PreparedOpportunityInput (string form)."""
    if value is None:
        return None
    return f"{value:.2f}"


def _aware_datetime(value: datetime | None) -> datetime | None:
    """Ensure a datetime has a timezone (assume Moscow, MSK = UTC+3)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_EIS_TZ)
    return value


class EisProjectionError(Exception):
    """Raised when projection to PreparedOpportunityInput fails."""


def project_to_prepared_input(
    notice: ParsedEisNotice,
) -> PreparedOpportunityInput:
    """Project a parsed ЕИС notice into a PreparedOpportunityInput.

    This is a pure, deterministic function — no AI, no fuzzy matching.
    """
    if not notice.procurement_number:
        raise EisProjectionError("Cannot project notice without procurement_number")
    if not notice.title:
        raise EisProjectionError("Cannot project notice without title")

    reg_number = notice.procurement_number.strip()

    # Collect all position texts for keyword matching
    all_position_texts: list[str] = []
    all_position_texts.append(notice.title)
    for pos in notice.positions:
        all_position_texts.append(pos.name)

    # Technology requirements from position names
    technology_requirements = _collect_technologies(all_position_texts)

    # Material requirements from position names
    material_requirements = _collect_materials(all_position_texts)

    # Status
    status = _map_status(notice.status_text)

    # Region code
    region_code = _map_region(notice.region)

    # Procurement type
    procurement_type = _map_method(notice.procurement_method)

    # Warranty text is captured for informational purposes but cannot be
    # projected into QualityRequirementInput without structured data
    # (IT grade, Ra, etc.).  Left as unresolved evidence.

    return PreparedOpportunityInput(
        source=SOURCE_CODE,
        external_id=reg_number,
        procurement_number=reg_number,
        title=notice.title[:500],
        customer=notice.customer[:500] if notice.customer else None,
        source_url=notice.source_url,
        status=status,
        procurement_type=procurement_type,
        okpd2_codes=notice.okpd2_codes or None,
        product_type_codes=None,
        material_requirements=material_requirements,
        technology_requirements=technology_requirements,
        equipment_requirements=None,
        dimensional_mass_requirements=None,
        quality_requirements=None,
        required_certificates=None,
        price_amount=_money_decimal(notice.max_price),
        price_currency=notice.currency,
        region_code=region_code,
        quantity=None,
        unit=None,
        application_deadline=_aware_datetime(notice.application_deadline),
        execution_deadline=None,
    )
