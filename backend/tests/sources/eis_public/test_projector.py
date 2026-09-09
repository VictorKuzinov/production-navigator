"""Tests for ЕИС → PreparedOpportunityInput projection.

Includes remediation tests for:
- EIS-05: conservative technology/material requirement semantics
  (never infer a manufacturing operation or material from mere substring
  presence; ambiguities stay unresolved).
- EIS-06: terminal states take precedence over OPEN phrasing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.procurement_opportunities import (
    ProcurementOpportunityStatus,
    RequirementStrength,
)
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.sources.eis_public.dto import ParsedEisNotice, ParsedEisPosition
from app.sources.eis_public.parser import parse_notice_html
from app.sources.eis_public.projector import (
    SOURCE_CODE,
    EisProjectionError,
    project_to_prepared_input,
)

# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------


def _base_notice(**overrides: object) -> ParsedEisNotice:
    defaults: dict[str, object] = {
        "procurement_number": "0373200049624000001",
        "title": "Тестовая закупка",
        "max_price": Decimal("1000000.00"),
        "currency": "RUB",
        "okpd2_codes": ["25.62.10.000"],
    }
    defaults.update(overrides)
    return ParsedEisNotice(**defaults)  # type: ignore[arg-type]


# -----------------------------------------------------------------------
# EIS-06: Status mapping
# -----------------------------------------------------------------------


class TestStatusMapping:
    def test_open(self) -> None:
        notice = _base_notice(status_text="Идёт прием заявок")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.OPEN

    def test_open_plain_submission(self) -> None:
        notice = _base_notice(status_text="Подача заявок")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.OPEN

    def test_closed(self) -> None:
        notice = _base_notice(status_text="Определение поставщика завершено")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.CLOSED

    def test_closed_on_completed_submission(self) -> None:
        """'Подача заявок завершена' must NOT be OPEN."""
        notice = _base_notice(status_text="Подача заявок завершена")
        result = project_to_prepared_input(notice)
        assert result.status != ProcurementOpportunityStatus.OPEN

    def test_closed_on_completed_determination(self) -> None:
        """'Определение поставщика завершено' → CLOSED."""
        notice = _base_notice(status_text="Определение поставщика завершено")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.CLOSED

    def test_cancelled(self) -> None:
        notice = _base_notice(status_text="Отменена")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.CANCELLED

    def test_awarded(self) -> None:
        notice = _base_notice(status_text="Контракт заключён")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.AWARDED

    def test_unknown(self) -> None:
        notice = _base_notice(status_text="Что-то непонятное")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.UNKNOWN

    def test_none_status(self) -> None:
        notice = _base_notice(status_text=None)
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.UNKNOWN

    def test_ambiguous_not_open(self) -> None:
        """Indistinct text without a recognised OPEN phrase must not resolve to OPEN."""
        notice = _base_notice(status_text="Прием документов")
        result = project_to_prepared_input(notice)
        assert result.status == ProcurementOpportunityStatus.UNKNOWN


# -----------------------------------------------------------------------
# Method mapping
# -----------------------------------------------------------------------


class TestMethodMapping:
    def test_electronic_quote(self) -> None:
        notice = _base_notice(
            procurement_method="Запрос котировок в электронной форме",
        )
        result = project_to_prepared_input(notice)
        assert result.procurement_type == "ELECTRONIC_QUOTE_REQUEST"

    def test_electronic_auction(self) -> None:
        notice = _base_notice(procurement_method="Электронный аукцион")
        result = project_to_prepared_input(notice)
        assert result.procurement_type == "ELECTRONIC_AUCTION"

    def test_unknown_method(self) -> None:
        notice = _base_notice(procurement_method="Что-то кастомное")
        result = project_to_prepared_input(notice)
        assert result.procurement_type is None


# -----------------------------------------------------------------------
# Region mapping
# -----------------------------------------------------------------------


class TestRegionMapping:
    def test_moscow(self) -> None:
        notice = _base_notice(region="Москва")
        result = project_to_prepared_input(notice)
        assert result.region_code == "PNC_REG_77"

    def test_moscow_oblast(self) -> None:
        notice = _base_notice(region="Московская область")
        result = project_to_prepared_input(notice)
        assert result.region_code == "PNC_REG_50"

    def test_unknown_region(self) -> None:
        notice = _base_notice(region="Непонятный регион")
        result = project_to_prepared_input(notice)
        assert result.region_code is None

    def test_none_region(self) -> None:
        notice = _base_notice(region=None)
        result = project_to_prepared_input(notice)
        assert result.region_code is None


# -----------------------------------------------------------------------
# EIS-05: Technology mapping (conservative)
# -----------------------------------------------------------------------


class TestTechnologyMapping:
    def test_turning_work(self) -> None:
        pos = ParsedEisPosition(name="Токарные работы по стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is not None
        codes = [t.technology_code for t in result.technology_requirements]
        assert "MACHINING" in codes

    def test_milling_work(self) -> None:
        pos = ParsedEisPosition(name="Фрезерные работы")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is not None
        codes = [t.technology_code for t in result.technology_requirements]
        assert "MACHINING" in codes

    def test_turning_and_milling_dedup(self) -> None:
        pos1 = ParsedEisPosition(name="Токарные работы")
        pos2 = ParsedEisPosition(name="Фрезерные работы")
        notice = _base_notice(positions=[pos1, pos2])
        result = project_to_prepared_input(notice)
        codes = [t.technology_code for t in result.technology_requirements]
        assert codes.count("MACHINING") == 1

    def test_thermal_cutting(self) -> None:
        pos = ParsedEisPosition(name="Плазменная резка металла")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        codes = [t.technology_code for t in result.technology_requirements]
        assert "PREPARATORY" in codes

    def test_drilling_work(self) -> None:
        pos = ParsedEisPosition(name="Сверлильные работы по металлу")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is not None
        codes = [t.technology_code for t in result.technology_requirements]
        assert "MACHINING" in codes

    def test_supply_of_turning_lathes_not_operation(self) -> None:
        """'Поставка токарных станков' is a deliverable, NOT a machining
        operation → no technology requirement."""
        pos = ParsedEisPosition(name="Поставка токарных станков")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is None

    def test_supply_of_drills_not_operation(self) -> None:
        """'Поставка сверл' is a deliverable, NOT a machining operation →
        'сверл' substring must not produce MACHINING."""
        pos = ParsedEisPosition(name="Поставка сверл")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is None

    def test_welding_unresolved(self) -> None:
        pos = ParsedEisPosition(name="Сварочные работы")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is None

    def test_no_positions(self) -> None:
        notice = _base_notice(positions=[])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is None


# -----------------------------------------------------------------------
# EIS-05: Material mapping (conservative)
# -----------------------------------------------------------------------


class TestMaterialMapping:
    def test_construction_steel(self) -> None:
        pos = ParsedEisPosition(name="по конструкционным сталям")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is not None
        codes = [m.material_group_code for m in result.material_requirements]
        assert "STEEL_CARBON" in codes

    def test_stainless_steel(self) -> None:
        pos = ParsedEisPosition(name="по нержавеющей стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        codes = [m.material_group_code for m in result.material_requirements]
        assert "STEEL_STAINLESS" in codes

    def test_alloy_steel(self) -> None:
        pos = ParsedEisPosition(name="по легированным сталям")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        codes = [m.material_group_code for m in result.material_requirements]
        assert "STEEL_ALLOY" in codes

    def test_low_alloy_steel_not_mapped(self) -> None:
        """'низколегированная сталь' must NOT become STEEL_ALLOY."""
        pos = ParsedEisPosition(name="по низколегированной стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is None

    def test_unalloyed_steel_not_mapped(self) -> None:
        """'нелегированная сталь' must NOT match 'легирован'."""
        pos = ParsedEisPosition(name="по нелегированной стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is None

    def test_high_temp_steel_unresolved(self) -> None:
        pos = ParsedEisPosition(name="жаропрочная сталь")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is None

    def test_mixed_phrase_not_split(self) -> None:
        """A mixed phrase listing several steels in one line must NOT
        produce multiple independent MANDATORY material groups — the whole
        line is treated as ambiguous and left unresolved."""
        pos = ParsedEisPosition(
            name="легированным сталям (нержавеющая сталь, жаропрочная сталь)",
        )
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is None

    def test_no_materials(self) -> None:
        pos = ParsedEisPosition(name="Общие работы")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is None


# -----------------------------------------------------------------------
# Requirement strength must remain MANDATORY for explicit matches
# -----------------------------------------------------------------------


class TestRequirementStrength:
    def test_technology_is_mandatory(self) -> None:
        pos = ParsedEisPosition(name="Токарные работы по стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.technology_requirements is not None
        for t in result.technology_requirements:
            assert t.requirement_strength == RequirementStrength.MANDATORY

    def test_material_is_mandatory(self) -> None:
        pos = ParsedEisPosition(name="по нержавеющей стали")
        notice = _base_notice(positions=[pos])
        result = project_to_prepared_input(notice)
        assert result.material_requirements is not None
        for m in result.material_requirements:
            assert m.requirement_strength == RequirementStrength.MANDATORY


# -----------------------------------------------------------------------
# Source / identity
# -----------------------------------------------------------------------


class TestSourceIdentity:
    def test_source_code(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        assert result.source == SOURCE_CODE

    def test_external_id_is_reg_number(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        assert result.external_id == notice.procurement_number

    def test_procurement_number_preserved(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        assert result.procurement_number == "0373200049624000001"


# -----------------------------------------------------------------------
# Full integration: parse fixture → project → validate PreparedOpportunityInput
# -----------------------------------------------------------------------


class TestFullPipeline:
    def test_sample_fixture(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        assert isinstance(result, PreparedOpportunityInput)
        assert result.source == "eis_public_44fz"
        assert result.external_id == "0373200049624000001"
        assert result.title
        assert result.status == ProcurementOpportunityStatus.CLOSED
        assert result.procurement_type == "ELECTRONIC_QUOTE_REQUEST"
        assert result.okpd2_codes == ["25.62.10.000"]
        assert result.price_amount == Decimal("1000000.00")
        assert result.price_currency == "RUB"
        assert result.region_code == "PNC_REG_77"
        assert result.application_deadline is not None

    def test_technologies_from_fixture(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        techs = result.technology_requirements
        assert techs is not None
        tech_codes = {t.technology_code for t in techs}
        assert "MACHINING" in tech_codes
        assert "PREPARATORY" in tech_codes

    def test_materials_from_fixture(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        mats = result.material_requirements
        assert mats is not None
        mat_codes = {m.material_group_code for m in mats}
        assert "STEEL_CARBON" in mat_codes
        assert "STEEL_STAINLESS" in mat_codes
        # STEEL_ALLOY must NOT be present: the fixture contains
        # 'легированным сталям (нержавеющая сталь, жаропрочная сталь)' —
        # "жаропрочная сталь" is ambiguous and must stay unresolved.
        assert "STEEL_ALLOY" not in mat_codes

    def test_unresolved_items(self, sample_html: str) -> None:
        """Welding and high-temp steel are NOT mapped."""
        notice = parse_notice_html(sample_html)
        result = project_to_prepared_input(notice)
        techs = result.technology_requirements or []
        tech_names = {t.technology_code for t in techs}
        assert "WELDING" not in tech_names
        assert result.equipment_requirements is None
        assert result.required_certificates is None


# -----------------------------------------------------------------------
# Error cases
# -----------------------------------------------------------------------


class TestProjectionErrors:
    def test_empty_procurement_number(self) -> None:
        notice = _base_notice(procurement_number="")
        with pytest.raises(EisProjectionError, match="procurement_number"):
            project_to_prepared_input(notice)

    def test_empty_title(self) -> None:
        notice = _base_notice(title="")
        with pytest.raises(EisProjectionError, match="title"):
            project_to_prepared_input(notice)
