from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.profile_capabilities import CapabilityState, ProfileSectionState
from app.schemas.procurement_matching import (
    AtomicMatchState,
    MatchAtomResult,
    MatchDimension,
    MatchFact,
    MatchSeverity,
    MaterialCapabilitySnapshot,
    ProfileMatchingSnapshot,
    QualityCapabilitySnapshot,
    UnknownOrigin,
)


def make_atom(**changes: object) -> MatchAtomResult:
    values: dict[str, object] = {
        "evidence_id": "a" * 64,
        "dimension": MatchDimension.OKPD2_CODES,
        "target_key": "25.62.10.000",
        "subfield": "code",
        "requirement_path": "okpd2_codes[0]",
        "requirement": MatchFact(
            path="okpd2_codes[0]",
            value="25.62.10.000",
        ),
        "state": AtomicMatchState.UNKNOWN,
        "severity": MatchSeverity.UNRESOLVED,
        "reason_code": "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING",
        "reason": "No approved mapping.",
        "origin": UnknownOrigin.MISSING_PROFILE_CAPABILITY,
    }
    values.update(changes)
    return MatchAtomResult.model_validate(values)


def test_matching_value_models_are_frozen_and_extra_forbidden() -> None:
    atom = make_atom()

    with pytest.raises(ValidationError, match="frozen"):
        atom.state = AtomicMatchState.MATCH
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MatchFact.model_validate({"path": "x", "value": 1, "score": 0.5})


@pytest.mark.parametrize(
    ("state", "severity", "origin"),
    [
        (AtomicMatchState.UNKNOWN, MatchSeverity.SOFT, UnknownOrigin.DATA_INTEGRITY),
        (AtomicMatchState.UNKNOWN, MatchSeverity.HARD, UnknownOrigin.DATA_INTEGRITY),
        (AtomicMatchState.MATCH, MatchSeverity.HARD, None),
        (AtomicMatchState.NOT_APPLICABLE, MatchSeverity.SOFT, None),
    ],
)
def test_atom_rejects_invalid_state_severity_combinations(
    state: AtomicMatchState,
    severity: MatchSeverity,
    origin: UnknownOrigin | None,
) -> None:
    with pytest.raises(ValidationError):
        make_atom(state=state, severity=severity, origin=origin)


def test_only_two_declared_reason_codes_can_be_hard() -> None:
    hard = make_atom(
        dimension=MatchDimension.MATERIAL_REQUIREMENTS,
        state=AtomicMatchState.MISMATCH,
        severity=MatchSeverity.HARD,
        origin=None,
        reason_code="HARD_MATERIAL_EXPLICIT_UNSUPPORTED",
        requirement_strength="MANDATORY",
    )
    assert hard.severity == MatchSeverity.HARD

    with pytest.raises(ValidationError, match="not an active Slice A hard rule"):
        make_atom(
            state=AtomicMatchState.MISMATCH,
            severity=MatchSeverity.HARD,
            origin=None,
            reason_code="HARD_EQUIPMENT_UNSUPPORTED",
            requirement_strength="MANDATORY",
        )


def test_material_snapshot_requires_exactly_one_target() -> None:
    valid = MaterialCapabilitySnapshot(
        capability_id=1,
        material_group_code="STEEL_CARBON",
        state=CapabilityState.SUPPORTED,
    )
    assert valid.material_id is None

    with pytest.raises(ValidationError, match="exactly one target"):
        MaterialCapabilitySnapshot(
            capability_id=1,
            material_group_code="STEEL_CARBON",
            material_id=2,
            state=CapabilityState.SUPPORTED,
        )


def test_result_contract_has_no_scoring_or_ranking_fields() -> None:
    forbidden = {"score", "weight", "rank", "top_10", "recommendation"}
    from app.schemas.procurement_matching import MatchResult

    assert forbidden.isdisjoint(MatchResult.model_fields)
    snapshot = ProfileMatchingSnapshot(
        profile_id=1,
        technology_section_state=ProfileSectionState.UNKNOWN,
        material_section_state=ProfileSectionState.UNKNOWN,
    )
    assert snapshot.model_dump()["quality_capability"] is None
    assert date(2026, 9, 3).isoformat() == "2026-09-03"


@pytest.mark.parametrize("invalid_grade", [-1, 0, 19, -100, 100])
def test_quality_snapshot_rejects_min_it_grade_outside_valid_range(
    invalid_grade: int,
) -> None:
    with pytest.raises(ValidationError, match="min_it_grade"):
        ProfileMatchingSnapshot(
            profile_id=1,
            technology_section_state=ProfileSectionState.UNKNOWN,
            material_section_state=ProfileSectionState.UNKNOWN,
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=invalid_grade,
                measuring_tools=False,
                cim_machine=False,
            ),
        )


@pytest.mark.parametrize("valid_grade", [1, 8, 18])
def test_quality_snapshot_accepts_valid_min_it_grade(valid_grade: int) -> None:
    snapshot = ProfileMatchingSnapshot(
        profile_id=1,
        technology_section_state=ProfileSectionState.UNKNOWN,
        material_section_state=ProfileSectionState.UNKNOWN,
        quality_capability=QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=valid_grade,
            measuring_tools=False,
            cim_machine=False,
        ),
    )
    assert snapshot.quality_capability is not None
    assert snapshot.quality_capability.min_it_grade == valid_grade


def test_equipment_snapshot_rejects_negative_working_zone() -> None:
    with pytest.raises(ValidationError, match="positive"):
        from app.schemas.procurement_matching import EquipmentSnapshot

        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            working_zone_x=Decimal("-100"),
        )


def test_equipment_snapshot_rejects_zero_max_diameter() -> None:
    with pytest.raises(ValidationError, match="positive"):
        from app.schemas.procurement_matching import EquipmentSnapshot

        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            max_diameter=Decimal("0"),
        )


def test_quality_snapshot_rejects_negative_min_ra() -> None:
    with pytest.raises(ValidationError, match="positive"):
        ProfileMatchingSnapshot(
            profile_id=1,
            technology_section_state=ProfileSectionState.UNKNOWN,
            material_section_state=ProfileSectionState.UNKNOWN,
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=7,
                min_ra=Decimal("-0.8"),
                measuring_tools=False,
                cim_machine=False,
            ),
        )


def test_quality_snapshot_rejects_zero_min_ra() -> None:
    with pytest.raises(ValidationError, match="positive"):
        ProfileMatchingSnapshot(
            profile_id=1,
            technology_section_state=ProfileSectionState.UNKNOWN,
            material_section_state=ProfileSectionState.UNKNOWN,
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=7,
                min_ra=Decimal("0"),
                measuring_tools=False,
                cim_machine=False,
            ),
        )
