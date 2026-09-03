from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.matching import ProcurementMatchingEngine
from app.matching.scoring import (
    ProcurementMatchingScoringEngine,
    calculate_scores,
    determine_match_status,
    top_matches,
)
from app.models.profile_capabilities import CapabilityState, ProfileSectionState
from app.schemas.procurement_matching import (
    EquipmentSnapshot,
    MatchEvaluationContext,
    OpportunityMatchIdentity,
    ProductExperienceSnapshot,
    ProfileMatchingSnapshot,
    QualityCapabilitySnapshot,
    TechnologyCapabilitySnapshot,
)
from app.schemas.procurement_matching_scoring import (
    CRITERION_ORDER,
    CRITERION_WEIGHTS,
    CriterionTrace,
    CriterionValue,
    MatchingCriterion,
    MatchStatus,
    RankingEvaluationContext,
)
from app.schemas.procurement_opportunities import PreparedOpportunityInput

EVALUATION_TIME = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def make_trace(
    values: dict[MatchingCriterion, CriterionValue],
    *,
    mandatory_remediable: MatchingCriterion | None = None,
) -> tuple[CriterionTrace, ...]:
    return tuple(
        CriterionTrace(
            criterion=criterion,
            weight=CRITERION_WEIGHTS[criterion],
            value=values.get(criterion, CriterionValue.NOT_APPLICABLE),
            evaluated_fraction=(
                Decimal(1)
                if values.get(criterion, CriterionValue.NOT_APPLICABLE)
                in {
                    CriterionValue.FULL,
                    CriterionValue.PARTIAL,
                    CriterionValue.ZERO,
                }
                else Decimal(0)
            ),
            mandatory=criterion == mandatory_remediable,
            remediable=criterion == mandatory_remediable,
        )
        for criterion in CRITERION_ORDER
    )


def make_opportunity(**changes: object) -> PreparedOpportunityInput:
    payload: dict[str, object] = {
        "source": "fixture",
        "external_id": "slice-b-1",
        "title": "Slice B opportunity",
        "status": "OPEN",
        "okpd2_codes": [],
        "product_type_codes": ["ASSEMBLY_UNIT"],
        "material_requirements": [],
        "technology_requirements": [],
        "equipment_requirements": [],
        "dimensional_mass_requirements": [],
        "quality_requirements": [],
        "required_certificates": [],
    }
    payload.update(changes)
    return PreparedOpportunityInput.model_validate(payload)


def make_profile(**changes: object) -> ProfileMatchingSnapshot:
    payload: dict[str, object] = {
        "profile_id": 7,
        "products": (
            ProductExperienceSnapshot(
                product_id=1,
                product_type_code="ASSEMBLY_UNIT",
            ),
        ),
        "technology_section_state": ProfileSectionState.CONFIRMED_COMPLETE,
        "material_section_state": ProfileSectionState.CONFIRMED_COMPLETE,
    }
    payload.update(changes)
    return ProfileMatchingSnapshot.model_validate(payload)


def score(
    opportunity: PreparedOpportunityInput,
    profile: ProfileMatchingSnapshot | None = None,
):
    profile = profile or make_profile()
    slice_a = ProcurementMatchingEngine().match(
        opportunity_id=11,
        opportunity=opportunity,
        profile=profile,
        context=MatchEvaluationContext(evaluation_date=EVALUATION_TIME.date()),
    )
    return ProcurementMatchingScoringEngine().score(
        opportunity,
        slice_a,
        RankingEvaluationContext(evaluation_time=EVALUATION_TIME),
    )


def trace_item(result, criterion: MatchingCriterion) -> CriterionTrace:
    return next(item for item in result.trace if item.criterion == criterion)


def test_v1_weights_are_exact_and_total_one_hundred() -> None:
    assert tuple(CRITERION_WEIGHTS) == CRITERION_ORDER
    assert tuple(CRITERION_WEIGHTS.values()) == (8, 23, 23, 15, 12, 5, 5, 3, 3, 3)
    assert sum(CRITERION_WEIGHTS.values()) == 100


def test_score_formula_handles_full_partial_and_soft_zero() -> None:
    trace = make_trace(
        {
            MatchingCriterion.PRODUCT_EXPERIENCE: CriterionValue.FULL,
            MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.PARTIAL,
            MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.ZERO,
        }
    )

    scores = calculate_scores(trace)

    expected_compatibility = (
        Decimal(100) * (Decimal(8) + Decimal(23) * Decimal("0.5")) / Decimal(54)
    )
    assert scores.compatibility_score == expected_compatibility
    assert scores.coverage == Decimal(1)
    assert scores.ranking_score == (
        Decimal("0.85") * expected_compatibility + Decimal("0.15") * Decimal(100)
    )


def test_unknown_is_excluded_from_compatibility_but_lowers_coverage() -> None:
    scores = calculate_scores(
        make_trace(
            {
                MatchingCriterion.PRODUCT_EXPERIENCE: CriterionValue.FULL,
                MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.UNKNOWN,
            }
        )
    )

    assert scores.compatibility_score == Decimal(100)
    assert scores.coverage == Decimal(8) / Decimal(31)
    assert scores.ranking_score == (
        Decimal(85) + Decimal(15) * Decimal(8) / Decimal(31)
    )


def test_not_applicable_is_excluded_from_both_denominators() -> None:
    scores = calculate_scores(
        make_trace({MatchingCriterion.PRODUCT_EXPERIENCE: CriterionValue.FULL})
    )

    assert scores.compatibility_score == Decimal(100)
    assert scores.coverage == Decimal(1)
    assert scores.ranking_score == Decimal(100)


def test_no_known_criteria_returns_null_compatibility_and_zero_ranking() -> None:
    scores = calculate_scores(
        make_trace({MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.UNKNOWN})
    )

    assert scores.compatibility_score is None
    assert scores.coverage == Decimal(0)
    assert scores.ranking_score == Decimal(0)


def test_status_priority_market_unavailable_wins_first() -> None:
    trace = make_trace(
        {MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.PARTIAL},
        mandatory_remediable=MatchingCriterion.MATERIAL_CAPABILITY,
    )
    status = determine_match_status(
        trace,
        calculate_scores(trace),
        market_unavailable=True,
        has_hard_conflict=True,
    )
    assert status == MatchStatus.NOT_ELIGIBLE


def test_status_priority_hard_conflict_wins_before_remediable() -> None:
    trace = make_trace(
        {MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.PARTIAL},
        mandatory_remediable=MatchingCriterion.MATERIAL_CAPABILITY,
    )
    status = determine_match_status(
        trace,
        calculate_scores(trace),
        market_unavailable=False,
        has_hard_conflict=True,
    )
    assert status == MatchStatus.INCOMPATIBLE


def test_mandatory_remediable_wins_over_high_score() -> None:
    trace = make_trace(
        {
            criterion: CriterionValue.FULL
            for criterion in CRITERION_ORDER
            if criterion != MatchingCriterion.MATERIAL_CAPABILITY
        }
        | {MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.PARTIAL},
        mandatory_remediable=MatchingCriterion.MATERIAL_CAPABILITY,
    )
    scores = calculate_scores(trace)

    assert scores.compatibility_score is not None
    assert scores.compatibility_score > Decimal(85)
    assert (
        determine_match_status(
            trace,
            scores,
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.POTENTIAL
    )


def test_low_coverage_returns_insufficient_data() -> None:
    trace = make_trace(
        {
            MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.FULL,
            MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.UNKNOWN,
            MatchingCriterion.EQUIPMENT_CAPABILITY: CriterionValue.UNKNOWN,
            MatchingCriterion.DIMENSIONS_MASS: CriterionValue.UNKNOWN,
            MatchingCriterion.QUALITY_CAPABILITY: CriterionValue.UNKNOWN,
        }
    )
    assert calculate_scores(trace).coverage < Decimal("0.35")
    assert (
        determine_match_status(
            trace,
            calculate_scores(trace),
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.INSUFFICIENT_DATA
    )


def test_no_evaluated_capability_returns_insufficient_even_with_full_coverage() -> None:
    trace = make_trace(
        {
            MatchingCriterion.PRODUCT_EXPERIENCE: CriterionValue.FULL,
            MatchingCriterion.QUANTITY_CAPACITY: CriterionValue.FULL,
        }
    )
    scores = calculate_scores(trace)
    assert scores.coverage == Decimal(1)
    assert (
        determine_match_status(
            trace,
            scores,
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.INSUFFICIENT_DATA
    )


def test_compatibility_below_fifty_returns_low_match() -> None:
    trace = make_trace(
        {
            MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.ZERO,
            MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.FULL,
            MatchingCriterion.EQUIPMENT_CAPABILITY: CriterionValue.ZERO,
        }
    )
    scores = calculate_scores(trace)
    assert scores.compatibility_score is not None
    assert scores.compatibility_score < Decimal(50)
    assert (
        determine_match_status(
            trace,
            scores,
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.LOW_MATCH
    )


@pytest.mark.parametrize(
    "trace",
    [
        make_trace(
            {
                MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.PARTIAL,
                MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.FULL,
                MatchingCriterion.PRODUCT_EXPERIENCE: CriterionValue.ZERO,
            }
        ),
        make_trace(
            {
                MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.FULL,
                MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.UNKNOWN,
            }
        ),
    ],
)
def test_score_or_coverage_threshold_returns_potential(
    trace: tuple[CriterionTrace, ...],
) -> None:
    scores = calculate_scores(trace)
    assert (scores.compatibility_score or Decimal(0)) < Decimal(
        75
    ) or scores.coverage < Decimal("0.60")
    assert (
        determine_match_status(
            trace,
            scores,
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.POTENTIAL
    )


def test_high_score_and_coverage_returns_match() -> None:
    trace = make_trace(
        {
            MatchingCriterion.MATERIAL_CAPABILITY: CriterionValue.FULL,
            MatchingCriterion.TECHNOLOGY_CAPABILITY: CriterionValue.FULL,
        }
    )
    scores = calculate_scores(trace)
    assert (
        determine_match_status(
            trace,
            scores,
            market_unavailable=False,
            has_hard_conflict=False,
        )
        == MatchStatus.MATCH
    )


@pytest.mark.parametrize("status", ["CLOSED", "CANCELLED", "AWARDED"])
def test_terminal_market_status_is_not_eligible(status: str) -> None:
    result = score(make_opportunity(status=status))

    assert result.match_status == MatchStatus.NOT_ELIGIBLE
    assert [reason.code for reason in result.eligibility_reasons] == [
        f"MARKET_STATUS_{status}"
    ]
    assert result.hard_conflicts == ()


@pytest.mark.parametrize(
    "deadline",
    [
        date(2026, 9, 2),
        EVALUATION_TIME - timedelta(microseconds=1),
    ],
)
def test_proven_expired_deadline_is_not_eligible(deadline) -> None:
    result = score(make_opportunity(application_deadline=deadline))

    assert result.match_status == MatchStatus.NOT_ELIGIBLE
    assert "APPLICATION_DEADLINE_EXPIRED" in {
        reason.code for reason in result.eligibility_reasons
    }


def test_date_only_deadline_remains_open_for_its_entire_calendar_date() -> None:
    result = score(make_opportunity(application_deadline=EVALUATION_TIME.date()))
    assert result.match_status != MatchStatus.NOT_ELIGIBLE


def test_explicit_time_context_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        RankingEvaluationContext(evaluation_time=datetime(2026, 9, 3, 12, 0))


def test_unknown_subatom_prevents_positive_criterion_score() -> None:
    opportunity = make_opportunity(
        product_type_codes=["ASSEMBLY_UNIT", "SHAFT"],
    )
    profile = make_profile(
        products=(
            ProductExperienceSnapshot(
                product_id=1,
                product_type_code="ASSEMBLY_UNIT",
            ),
            ProductExperienceSnapshot(product_id=2, product_type_code="SHAFT"),
        )
    )

    result = score(opportunity, profile)

    product = trace_item(result, MatchingCriterion.PRODUCT_EXPERIENCE)
    assert product.value == CriterionValue.UNKNOWN
    assert product.evaluated_fraction == 0
    assert product.unresolved_evidence_ids
    assert "AMBIGUOUS_REQUIREMENT_GROUPING" in product.reason_codes
    assert result.compatibility_score is None
    assert (
        sum(
            reason.criterion.value == MatchingCriterion.PRODUCT_EXPERIENCE.value
            for reason in result.positive_reasons
        )
        == 2
    )


def test_preferred_unknown_preserves_confirmed_subatom_and_reduces_coverage() -> None:
    opportunity = make_opportunity(
        product_type_codes=[],
        equipment_requirements=[
            {
                "equipment_type_code": "TURNING_CENTER",
                "cnc": False,
                "requirement_strength": "PREFERRED",
            }
        ],
    )
    result = score(
        opportunity,
        make_profile(
            equipments=(
                EquipmentSnapshot(
                    equipment_id=1,
                    equipment_type_code="TURNING_CENTER",
                    cnc=False,
                    quantity=1,
                ),
            )
        ),
    )

    equipment = trace_item(result, MatchingCriterion.EQUIPMENT_CAPABILITY)
    assert equipment.value == CriterionValue.FULL
    assert equipment.evaluated_fraction == Decimal("0.5")
    assert len(equipment.unresolved_evidence_ids) == 1
    assert result.compatibility_score == Decimal(100)
    assert result.coverage == Decimal("7.5") / Decimal(28)
    assert "AMBIGUOUS_CNC_FALSE_SEMANTICS" in {
        reason.code for reason in result.missing_data
    }
    assert "EQUIPMENT_TYPE_PRESENT" in {
        reason.code for reason in result.positive_reasons
    }


def test_mandatory_unknown_blocks_criterion_but_keeps_confirmed_evidence() -> None:
    opportunity = make_opportunity(
        product_type_codes=[],
        equipment_requirements=[
            {
                "equipment_type_code": "TURNING_CENTER",
                "cnc": False,
                "requirement_strength": "MANDATORY",
            }
        ],
    )
    result = score(
        opportunity,
        make_profile(
            equipments=(
                EquipmentSnapshot(
                    equipment_id=1,
                    equipment_type_code="TURNING_CENTER",
                    cnc=False,
                    quantity=1,
                ),
            )
        ),
    )

    equipment = trace_item(result, MatchingCriterion.EQUIPMENT_CAPABILITY)
    assert equipment.value == CriterionValue.UNKNOWN
    assert equipment.evaluated_fraction == 0
    assert result.compatibility_score is None
    assert "EQUIPMENT_TYPE_PRESENT" in {
        reason.code for reason in result.positive_reasons
    }
    assert "AMBIGUOUS_CNC_FALSE_SEMANTICS" in {
        reason.code for reason in result.missing_data
    }


def test_partial_value_comes_only_from_mixed_determinate_subatoms() -> None:
    opportunity = make_opportunity(
        product_type_codes=[],
        quality_requirements=[
            {
                "required_it_grade": 7,
                "measuring_capability_required": True,
                "cmm_required": True,
                "requirement_strength": "PREFERRED",
            }
        ],
    )
    result = score(
        opportunity,
        make_profile(
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=9,
                measuring_tools=True,
                cim_machine=True,
            )
        ),
    )

    quality = trace_item(result, MatchingCriterion.QUALITY_CAPABILITY)
    assert quality.value == CriterionValue.PARTIAL
    assert quality.evaluated_fraction == Decimal(2) / Decimal(3)
    assert result.compatibility_score == Decimal(50)
    assert result.coverage == Decimal(2) / Decimal(16)
    assert "AMBIGUOUS_CMM_CAPABILITY_MAPPING" in {
        reason.code for reason in result.missing_data
    }


def test_current_quantity_deadline_and_logistics_are_uncovered() -> None:
    result = score(
        make_opportunity(
            quantity="100.000000",
            unit="PCS",
            execution_deadline=date(2026, 12, 1),
            region_code="RU-SVE",
        )
    )

    for criterion in (
        MatchingCriterion.QUANTITY_CAPACITY,
        MatchingCriterion.EXECUTION_DEADLINE,
        MatchingCriterion.REGION_LOGISTICS,
    ):
        assert trace_item(result, criterion).value == CriterionValue.UNKNOWN
    assert {reason.code for reason in result.missing_capabilities} >= {
        "COMPARABLE_CAPACITY_NOT_AVAILABLE",
        "EARLIEST_FEASIBLE_COMPLETION_NOT_AVAILABLE",
        "PROFILE_LOGISTICS_CAPABILITY_NOT_AVAILABLE",
    }


def test_hard_conflict_is_separate_from_market_eligibility() -> None:
    opportunity = make_opportunity(
        technology_requirements=[
            {
                "technology_code": "TURNING",
                "requirement_strength": "MANDATORY",
            }
        ]
    )
    profile = make_profile(
        technology_capabilities=(
            TechnologyCapabilitySnapshot(
                capability_id=3,
                technology_code="TURNING",
                state=CapabilityState.UNSUPPORTED,
            ),
        )
    )

    result = score(opportunity, profile)

    assert result.match_status == MatchStatus.INCOMPATIBLE
    assert result.eligibility_reasons == ()
    assert [item.code for item in result.hard_conflicts] == [
        "HARD_TECHNOLOGY_EXPLICIT_UNSUPPORTED"
    ]


def ranked_copy(
    result,
    *,
    external_id: str,
    status: MatchStatus = MatchStatus.MATCH,
    ranking: str = "80",
    coverage: str = "0.8",
    deadline=None,
    source: str = "fixture",
):
    identity = OpportunityMatchIdentity(source=source, external_id=external_id)
    slice_a = result.slice_a_result.model_copy(
        update={"opportunity_identity": identity}
    )
    return result.model_copy(
        update={
            "opportunity_identity": identity,
            "match_status": status,
            "ranking_score": Decimal(ranking),
            "coverage": Decimal(coverage),
            "application_deadline": deadline,
            "slice_a_result": slice_a,
        }
    )


def test_top_ten_excludes_only_not_eligible_and_incompatible() -> None:
    base = score(make_opportunity())
    statuses = tuple(MatchStatus)
    results = [
        ranked_copy(base, external_id=str(index), status=status)
        for index, status in enumerate(statuses)
    ]

    ranked = top_matches(results)

    assert {item.match_status for item in ranked} == {
        MatchStatus.POTENTIAL,
        MatchStatus.INSUFFICIENT_DATA,
        MatchStatus.LOW_MATCH,
        MatchStatus.MATCH,
    }


def test_top_ten_uses_all_tie_breakers_and_preserves_deadline_shape() -> None:
    base = score(make_opportunity())
    same_day = date(2026, 10, 1)
    results = (
        ranked_copy(base, external_id="null", deadline=None),
        ranked_copy(
            base,
            external_id="datetime",
            deadline=datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        ),
        ranked_copy(base, external_id="date", deadline=same_day),
        ranked_copy(base, source="alpha", external_id="b", deadline=same_day),
        ranked_copy(base, source="alpha", external_id="a", deadline=same_day),
    )

    ranked = top_matches(results)

    assert [
        (item.opportunity_identity.source, item.opportunity_identity.external_id)
        for item in ranked
    ] == [
        ("alpha", "a"),
        ("alpha", "b"),
        ("fixture", "date"),
        ("fixture", "datetime"),
        ("fixture", "null"),
    ]


def test_top_ten_orders_score_then_coverage_and_handles_both_cardinalities() -> None:
    base = score(make_opportunity())
    three = [
        ranked_copy(
            base,
            external_id=str(index),
            ranking=str(70 + index),
            coverage=str(Decimal("0.5") + Decimal(index) / Decimal(100)),
        )
        for index in range(3)
    ]
    assert len(top_matches(three)) == 3

    twelve = [
        ranked_copy(
            base,
            external_id=f"{index:02d}",
            ranking="80",
            coverage=str(Decimal(index) / Decimal(12)),
        )
        for index in range(12)
    ]
    first = top_matches(twelve)
    second = top_matches(reversed(twelve))

    assert len(first) == 10
    assert [item.opportunity_identity.external_id for item in first] == [
        f"{index:02d}" for index in range(11, 1, -1)
    ]
    assert [item.opportunity_identity.external_id for item in first] == [
        item.opportunity_identity.external_id for item in second
    ]
