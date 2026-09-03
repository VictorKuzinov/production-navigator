from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.matching import ProcurementMatchingEngine
from app.models.profile_capabilities import CapabilityState, ProfileSectionState
from app.schemas.procurement_matching import (
    MATCH_DIMENSION_ORDER,
    AtomicMatchState,
    CertificateSnapshot,
    DimensionMatchState,
    EquipmentSnapshot,
    MatchDimension,
    MatchEvaluationContext,
    MatchSeverity,
    MaterialCapabilitySnapshot,
    PairMatchVerdict,
    ProductExperienceSnapshot,
    ProfileMatchingSnapshot,
    QualityCapabilitySnapshot,
    TechnologyCapabilitySnapshot,
    UnknownOrigin,
)
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.seeds.procurement_opportunities import load_bundled_document

EVALUATION_DATE = date(2026, 9, 3)


def make_opportunity(**changes: object) -> PreparedOpportunityInput:
    payload: dict[str, object] = {
        "source": "fixture",
        "external_id": "matching-1",
        "title": "Matching opportunity",
        "status": "OPEN",
        "okpd2_codes": ["25.62.10.000"],
        "product_type_codes": None,
        "material_requirements": None,
        "technology_requirements": None,
        "equipment_requirements": None,
        "dimensional_mass_requirements": None,
        "quality_requirements": None,
        "required_certificates": None,
    }
    payload.update(changes)
    return PreparedOpportunityInput.model_validate(payload)


def make_profile(**changes: object) -> ProfileMatchingSnapshot:
    payload: dict[str, object] = {
        "profile_id": 7,
        "technology_section_state": ProfileSectionState.UNKNOWN,
        "material_section_state": ProfileSectionState.UNKNOWN,
    }
    payload.update(changes)
    return ProfileMatchingSnapshot.model_validate(payload)


def match(
    opportunity: PreparedOpportunityInput,
    profile: ProfileMatchingSnapshot | None = None,
):
    return ProcurementMatchingEngine().match(
        opportunity_id=11,
        opportunity=opportunity,
        profile=profile or make_profile(),
        context=MatchEvaluationContext(evaluation_date=EVALUATION_DATE),
    )


def dimension(result, name: MatchDimension):
    return next(item for item in result.dimensions if item.dimension == name)


def atom(result, name: MatchDimension, subfield: str):
    return next(
        item for item in dimension(result, name).atoms if item.subfield == subfield
    )


def test_always_returns_eight_dimensions_in_fixed_order_and_distinguishes_tri_state():
    unknown = match(make_opportunity(product_type_codes=None))
    empty = match(make_opportunity(product_type_codes=[]))
    known = match(
        make_opportunity(product_type_codes=["ASSEMBLY_UNIT"]),
        make_profile(
            products=(
                ProductExperienceSnapshot(
                    product_id=1,
                    product_type_code="ASSEMBLY_UNIT",
                ),
            )
        ),
    )

    assert tuple(item.dimension for item in unknown.dimensions) == MATCH_DIMENSION_ORDER
    assert (
        dimension(unknown, MatchDimension.PRODUCT_TYPE_CODES).state
        == DimensionMatchState.UNKNOWN
    )
    assert (
        dimension(empty, MatchDimension.PRODUCT_TYPE_CODES).state
        == DimensionMatchState.NOT_APPLICABLE
    )
    assert (
        dimension(known, MatchDimension.PRODUCT_TYPE_CODES).state
        == DimensionMatchState.MATCH
    )
    assert (
        atom(unknown, MatchDimension.PRODUCT_TYPE_CODES, "collection").origin
        == UnknownOrigin.PROCUREMENT_SOURCE
    )


def test_product_experience_and_okpd2_are_independent_soft_and_unknown_signals():
    result = match(
        make_opportunity(product_type_codes=["ASSEMBLY_UNIT"]),
        make_profile(
            products=(
                ProductExperienceSnapshot(
                    product_id=1,
                    product_type_code="ASSEMBLY_UNIT",
                ),
            )
        ),
    )

    product_atom = atom(
        result,
        MatchDimension.PRODUCT_TYPE_CODES,
        "product_type_code",
    )
    okpd_atom = atom(result, MatchDimension.OKPD2_CODES, "code")
    assert (product_atom.state, product_atom.severity) == (
        AtomicMatchState.MATCH,
        MatchSeverity.SOFT,
    )
    assert okpd_atom.reason_code == "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING"
    assert okpd_atom.state == AtomicMatchState.UNKNOWN


@pytest.mark.parametrize(
    ("specific_state", "expected_state", "expected_hard"),
    [
        (CapabilityState.SUPPORTED, AtomicMatchState.MATCH, False),
        (CapabilityState.UNKNOWN, AtomicMatchState.UNKNOWN, False),
        (CapabilityState.UNSUPPORTED, AtomicMatchState.MISMATCH, True),
    ],
)
def test_exact_material_precedes_group_and_only_explicit_mandatory_unsupported_is_hard(
    specific_state: CapabilityState,
    expected_state: AtomicMatchState,
    expected_hard: bool,
):
    opportunity = make_opportunity(
        material_requirements=[
            {
                "material_group_code": "STEEL_CARBON",
                "material_id": 42,
                "requirement_strength": "MANDATORY",
            }
        ]
    )
    profile = make_profile(
        material_section_state=ProfileSectionState.CONFIRMED_COMPLETE,
        material_capabilities=(
            MaterialCapabilitySnapshot(
                capability_id=1,
                material_group_code="STEEL_CARBON",
                state=CapabilityState.SUPPORTED,
            ),
            MaterialCapabilitySnapshot(
                capability_id=2,
                material_id=42,
                state=specific_state,
            ),
        ),
    )

    result = match(opportunity, profile)
    material_atom = atom(
        result,
        MatchDimension.MATERIAL_REQUIREMENTS,
        "capability_state",
    )

    assert material_atom.state == expected_state
    assert (material_atom.severity == MatchSeverity.HARD) is expected_hard
    assert (result.verdict == PairMatchVerdict.HARD_INCOMPATIBLE) is expected_hard
    assert material_atom.resolution_path == ("material_capability:2",)


@pytest.mark.parametrize(
    ("section_state", "expected_state", "expected_reason"),
    [
        (
            ProfileSectionState.CONFIRMED_COMPLETE,
            AtomicMatchState.MISMATCH,
            "CAPABILITY_NOT_ASSERTED_COMPLETE_SECTION",
        ),
        (
            ProfileSectionState.PARTIAL,
            AtomicMatchState.UNKNOWN,
            "CAPABILITY_NOT_ASSERTED_INCOMPLETE_SECTION",
        ),
        (
            ProfileSectionState.UNKNOWN,
            AtomicMatchState.UNKNOWN,
            "CAPABILITY_NOT_ASSERTED_INCOMPLETE_SECTION",
        ),
    ],
)
def test_technology_no_assertion_is_section_aware_but_never_hard(
    section_state: ProfileSectionState,
    expected_state: AtomicMatchState,
    expected_reason: str,
):
    result = match(
        make_opportunity(
            technology_requirements=[
                {
                    "technology_code": "TURNING",
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(technology_section_state=section_state),
    )
    technology_atom = atom(
        result,
        MatchDimension.TECHNOLOGY_REQUIREMENTS,
        "capability_state",
    )
    assert technology_atom.state == expected_state
    assert technology_atom.reason_code == expected_reason
    assert technology_atom.severity != MatchSeverity.HARD


def test_single_mandatory_explicit_unsupported_technology_is_the_second_hard_rule():
    result = match(
        make_opportunity(
            technology_requirements=[
                {
                    "technology_code": "TURNING",
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            technology_capabilities=(
                TechnologyCapabilitySnapshot(
                    capability_id=3,
                    technology_code="TURNING",
                    state=CapabilityState.UNSUPPORTED,
                ),
            )
        ),
    )
    technology_atom = atom(
        result,
        MatchDimension.TECHNOLOGY_REQUIREMENTS,
        "capability_state",
    )
    assert technology_atom.reason_code == "HARD_TECHNOLOGY_EXPLICIT_UNSUPPORTED"
    assert result.hard_incompatibility_evidence_ids == (technology_atom.evidence_id,)


def test_multi_item_grouping_is_unknown_and_suppresses_hard_evidence():
    result = match(
        make_opportunity(
            technology_requirements=[
                {
                    "technology_code": "TURNING",
                    "requirement_strength": "MANDATORY",
                },
                {
                    "technology_code": "MILLING",
                    "requirement_strength": "MANDATORY",
                },
            ]
        ),
        make_profile(
            technology_capabilities=(
                TechnologyCapabilitySnapshot(
                    capability_id=1,
                    technology_code="TURNING",
                    state=CapabilityState.UNSUPPORTED,
                ),
                TechnologyCapabilitySnapshot(
                    capability_id=2,
                    technology_code="MILLING",
                    state=CapabilityState.UNSUPPORTED,
                ),
            )
        ),
    )

    grouping = atom(
        result,
        MatchDimension.TECHNOLOGY_REQUIREMENTS,
        "grouping",
    )
    assert grouping.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING"
    assert result.hard_incompatibility_evidence_ids == ()
    assert result.verdict == PairMatchVerdict.UNDETERMINED


@pytest.mark.parametrize("profile_cnc", [True, False])
def test_procurement_cnc_false_is_always_ambiguous(profile_cnc: bool):
    result = match(
        make_opportunity(
            equipment_requirements=[
                {
                    "equipment_type_code": "TURNING",
                    "cnc": False,
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            equipments=(
                EquipmentSnapshot(
                    equipment_id=1,
                    equipment_type_code="TURNING",
                    cnc=profile_cnc,
                    axes=3,
                    quantity=1,
                ),
            )
        ),
    )
    cnc_atom = atom(result, MatchDimension.EQUIPMENT_REQUIREMENTS, "cnc")
    assert cnc_atom.state == AtomicMatchState.UNKNOWN
    assert cnc_atom.reason_code == "AMBIGUOUS_CNC_FALSE_SEMANTICS"
    assert cnc_atom.origin == UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS


def test_cnc_true_and_axes_create_positive_only_soft_evidence():
    opportunity = make_opportunity(
        equipment_requirements=[
            {
                "equipment_type_code": "TURNING",
                "cnc": True,
                "axes": 4,
                "working_zone_x_mm": "500.000",
                "requirement_strength": "PREFERRED",
            }
        ]
    )
    profile = make_profile(
        equipments=(
            EquipmentSnapshot(
                equipment_id=2,
                equipment_type_code="TURNING",
                cnc=True,
                axes=5,
                quantity=1,
                working_zone_x="500",
            ),
        )
    )
    result = match(opportunity, profile)

    assert (
        atom(result, MatchDimension.EQUIPMENT_REQUIREMENTS, "cnc").state
        == AtomicMatchState.MATCH
    )
    assert (
        atom(result, MatchDimension.EQUIPMENT_REQUIREMENTS, "axes").state
        == AtomicMatchState.MATCH
    )
    zone = atom(
        result,
        MatchDimension.EQUIPMENT_REQUIREMENTS,
        "working_zone_x_mm",
    )
    assert zone.reason_code == "PROFILE_EQUIPMENT_UNIT_NOT_DECLARED"
    assert zone.state == AtomicMatchState.UNKNOWN


def test_cnc_true_with_only_profile_false_default_is_unknown_not_negative():
    result = match(
        make_opportunity(
            equipment_requirements=[
                {
                    "equipment_type_code": "TURNING",
                    "cnc": True,
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            equipments=(
                EquipmentSnapshot(
                    equipment_id=1,
                    equipment_type_code="TURNING",
                    cnc=False,
                    quantity=1,
                ),
            )
        ),
    )
    cnc = atom(result, MatchDimension.EQUIPMENT_REQUIREMENTS, "cnc")
    assert cnc.state == AtomicMatchState.UNKNOWN
    assert cnc.reason_code == "PROFILE_EQUIPMENT_CNC_NOT_PROVEN"
    assert cnc.severity == MatchSeverity.UNRESOLVED


@pytest.mark.parametrize("cim_machine", [True, False])
def test_quality_keeps_it_rule_but_never_compares_ra_or_maps_cmm(cim_machine: bool):
    result = match(
        make_opportunity(
            quality_requirements=[
                {
                    "required_it_grade": 8,
                    "maximum_ra_um": "1.6000",
                    "cmm_required": True,
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=7,
                min_ra="0.8",
                measuring_tools=False,
                cim_machine=cim_machine,
            )
        ),
    )
    assert (
        atom(result, MatchDimension.QUALITY_REQUIREMENTS, "required_it_grade").state
        == AtomicMatchState.MATCH
    )
    ra = atom(result, MatchDimension.QUALITY_REQUIREMENTS, "maximum_ra_um")
    cmm = atom(result, MatchDimension.QUALITY_REQUIREMENTS, "cmm_required")
    assert (ra.state, ra.reason_code) == (
        AtomicMatchState.UNKNOWN,
        "PROFILE_QUALITY_UNIT_NOT_DECLARED",
    )
    assert (cmm.state, cmm.reason_code) == (
        AtomicMatchState.UNKNOWN,
        "AMBIGUOUS_CMM_CAPABILITY_MAPPING",
    )


@pytest.mark.parametrize(
    ("profile_grade", "required_grade", "expected_state"),
    [
        (7, 8, AtomicMatchState.MATCH),
        (8, 8, AtomicMatchState.MATCH),
        (9, 8, AtomicMatchState.MISMATCH),
    ],
)
def test_it_grade_comparator_boundaries(
    profile_grade: int,
    required_grade: int,
    expected_state: AtomicMatchState,
):
    result = match(
        make_opportunity(
            quality_requirements=[
                {
                    "required_it_grade": required_grade,
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_it_grade=profile_grade,
                measuring_tools=False,
                cim_machine=False,
            )
        ),
    )
    it_grade = atom(
        result,
        MatchDimension.QUALITY_REQUIREMENTS,
        "required_it_grade",
    )
    assert it_grade.state == expected_state
    assert it_grade.severity == MatchSeverity.SOFT


def test_profile_measuring_false_default_is_unknown_not_negative():
    result = match(
        make_opportunity(
            quality_requirements=[
                {
                    "measuring_capability_required": True,
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                measuring_tools=False,
                cim_machine=False,
            )
        ),
    )
    measuring = atom(
        result,
        MatchDimension.QUALITY_REQUIREMENTS,
        "measuring_capability_required",
    )
    assert measuring.state == AtomicMatchState.UNKNOWN
    assert measuring.severity == MatchSeverity.UNRESOLVED


def test_certificate_current_validity_is_soft_positive_but_dates_stay_unknown():
    result = match(
        make_opportunity(
            required_certificates=[
                {
                    "certificate_type_code": "PNC_CERT_ISO9001",
                    "requirement_strength": "MANDATORY",
                    "required_by": "2026-09-01",
                    "valid_through": "2027-09-01",
                }
            ]
        ),
        make_profile(
            certificates=(
                CertificateSnapshot(
                    certificate_id=4,
                    certificate_type_code="PNC_CERT_ISO9001",
                    issue_date=date(2026, 1, 1),
                    expiry_date=date(2026, 12, 31),
                ),
            )
        ),
    )
    current = atom(
        result,
        MatchDimension.REQUIRED_CERTIFICATES,
        "certificate_type_currently_valid",
    )
    required_by = atom(
        result,
        MatchDimension.REQUIRED_CERTIFICATES,
        "required_by",
    )
    valid_through = atom(
        result,
        MatchDimension.REQUIRED_CERTIFICATES,
        "valid_through",
    )
    assert (current.state, current.severity) == (
        AtomicMatchState.MATCH,
        MatchSeverity.SOFT,
    )
    assert required_by.reason_code == "AMBIGUOUS_CERTIFICATE_REQUIRED_BY_SEMANTICS"
    assert valid_through.reason_code == "AMBIGUOUS_CERTIFICATE_VALID_THROUGH_SEMANTICS"
    assert (
        dimension(result, MatchDimension.REQUIRED_CERTIFICATES).state
        == DimensionMatchState.PARTIAL
    )


def test_dimensional_mass_has_no_surrogate_capability():
    result = match(
        make_opportunity(
            dimensional_mass_requirements=[
                {
                    "length_mm": "100.000",
                    "mass_kg": "10.000",
                    "requirement_strength": "MANDATORY",
                }
            ]
        )
    )
    assert (
        atom(
            result,
            MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS,
            "length_mm",
        ).reason_code
        == "AMBIGUOUS_DIMENSIONAL_ENVELOPE_SEMANTICS"
    )
    assert (
        atom(
            result,
            MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS,
            "mass_kg",
        ).reason_code
        == "MISSING_PROFILE_CAPABILITY_MAX_WORKPIECE_MASS"
    )


def test_repeated_runs_and_reordered_input_collections_are_byte_equivalent():
    first = make_opportunity(
        okpd2_codes=["25.62.10.000", "25.62.20.000"],
        product_type_codes=["STANDARD_PARTS", "ASSEMBLY_UNIT"],
    )
    second = make_opportunity(
        okpd2_codes=["25.62.20.000", "25.62.10.000"],
        product_type_codes=["ASSEMBLY_UNIT", "STANDARD_PARTS"],
    )
    profile = make_profile(
        products=(
            ProductExperienceSnapshot(
                product_id=2,
                product_type_code="STANDARD_PARTS",
            ),
            ProductExperienceSnapshot(
                product_id=1,
                product_type_code="ASSEMBLY_UNIT",
            ),
        )
    )

    result_a = match(first, profile)
    result_b = match(second, profile)
    result_c = match(first, profile)

    assert result_a.model_dump_json() == result_b.model_dump_json()
    assert result_a.model_dump_json() == result_c.model_dump_json()


@pytest.mark.parametrize(
    ("field", "match_dimension", "known_value", "profile", "known_state"),
    [
        (
            "okpd2_codes",
            MatchDimension.OKPD2_CODES,
            ["25.62.10.000"],
            make_profile(),
            DimensionMatchState.UNKNOWN,
        ),
        (
            "product_type_codes",
            MatchDimension.PRODUCT_TYPE_CODES,
            ["ASSEMBLY_UNIT"],
            make_profile(
                products=(
                    ProductExperienceSnapshot(
                        product_id=1,
                        product_type_code="ASSEMBLY_UNIT",
                    ),
                )
            ),
            DimensionMatchState.MATCH,
        ),
        (
            "material_requirements",
            MatchDimension.MATERIAL_REQUIREMENTS,
            [
                {
                    "material_group_code": "STEEL_CARBON",
                    "requirement_strength": "PREFERRED",
                }
            ],
            make_profile(
                material_capabilities=(
                    MaterialCapabilitySnapshot(
                        capability_id=1,
                        material_group_code="STEEL_CARBON",
                        state=CapabilityState.SUPPORTED,
                    ),
                )
            ),
            DimensionMatchState.MATCH,
        ),
        (
            "technology_requirements",
            MatchDimension.TECHNOLOGY_REQUIREMENTS,
            [
                {
                    "technology_code": "TURNING",
                    "requirement_strength": "PREFERRED",
                }
            ],
            make_profile(
                technology_capabilities=(
                    TechnologyCapabilitySnapshot(
                        capability_id=1,
                        technology_code="TURNING",
                        state=CapabilityState.SUPPORTED,
                    ),
                )
            ),
            DimensionMatchState.MATCH,
        ),
        (
            "equipment_requirements",
            MatchDimension.EQUIPMENT_REQUIREMENTS,
            [
                {
                    "equipment_type_code": "TURNING",
                    "requirement_strength": "PREFERRED",
                }
            ],
            make_profile(
                equipments=(
                    EquipmentSnapshot(
                        equipment_id=1,
                        equipment_type_code="TURNING",
                        cnc=False,
                        quantity=1,
                    ),
                )
            ),
            DimensionMatchState.MATCH,
        ),
        (
            "dimensional_mass_requirements",
            MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS,
            [{"mass_kg": "10.000", "requirement_strength": "PREFERRED"}],
            make_profile(),
            DimensionMatchState.UNKNOWN,
        ),
        (
            "quality_requirements",
            MatchDimension.QUALITY_REQUIREMENTS,
            [{"required_it_grade": 8, "requirement_strength": "PREFERRED"}],
            make_profile(
                quality_capability=QualityCapabilitySnapshot(
                    capability_id=1,
                    min_it_grade=8,
                    measuring_tools=False,
                    cim_machine=False,
                )
            ),
            DimensionMatchState.MATCH,
        ),
        (
            "required_certificates",
            MatchDimension.REQUIRED_CERTIFICATES,
            [
                {
                    "certificate_type_code": "PNC_CERT_ISO9001",
                    "requirement_strength": "PREFERRED",
                }
            ],
            make_profile(
                certificates=(
                    CertificateSnapshot(
                        certificate_id=1,
                        certificate_type_code="PNC_CERT_ISO9001",
                        issue_date=date(2026, 1, 1),
                        expiry_date=date(2026, 12, 31),
                    ),
                )
            ),
            DimensionMatchState.MATCH,
        ),
    ],
)
def test_every_dimension_preserves_null_empty_and_known_semantics(
    field: str,
    match_dimension: MatchDimension,
    known_value: list[object],
    profile: ProfileMatchingSnapshot,
    known_state: DimensionMatchState,
):
    support = (
        {"product_type_codes": ["ASSEMBLY_UNIT"]} if field == "okpd2_codes" else {}
    )
    unknown = match(make_opportunity(**support, **{field: None}), profile)
    empty = match(make_opportunity(**support, **{field: []}), profile)
    known = match(make_opportunity(**support, **{field: known_value}), profile)

    unknown_dimension = dimension(unknown, match_dimension)
    empty_dimension = dimension(empty, match_dimension)
    known_dimension = dimension(known, match_dimension)
    assert unknown_dimension.state == DimensionMatchState.UNKNOWN
    assert unknown_dimension.atoms[0].origin == UnknownOrigin.PROCUREMENT_SOURCE
    assert empty_dimension.state == DimensionMatchState.NOT_APPLICABLE
    assert known_dimension.state == known_state
    assert known_dimension.atoms[0].reason_code != "PROCUREMENT_REQUIREMENT_UNKNOWN"


@pytest.mark.parametrize("strength", ["PREFERRED", "UNKNOWN"])
def test_nonmandatory_explicit_unsupported_capability_is_only_soft(strength: str):
    result = match(
        make_opportunity(
            technology_requirements=[
                {
                    "technology_code": "TURNING",
                    "requirement_strength": strength,
                }
            ]
        ),
        make_profile(
            technology_capabilities=(
                TechnologyCapabilitySnapshot(
                    capability_id=1,
                    technology_code="TURNING",
                    state=CapabilityState.UNSUPPORTED,
                ),
            )
        ),
    )
    technology_atom = atom(
        result,
        MatchDimension.TECHNOLOGY_REQUIREMENTS,
        "capability_state",
    )
    assert technology_atom.state == AtomicMatchState.MISMATCH
    assert technology_atom.severity == MatchSeverity.SOFT
    assert result.hard_incompatibility_evidence_ids == ()


@pytest.mark.parametrize("min_ra", ["0.8", "3.2", None])
def test_ra_is_unknown_for_mathematical_match_mismatch_and_missing_fact(
    min_ra: str | None,
):
    profile = make_profile()
    if min_ra is not None:
        profile = make_profile(
            quality_capability=QualityCapabilitySnapshot(
                capability_id=1,
                min_ra=min_ra,
                measuring_tools=False,
                cim_machine=False,
            )
        )
    result = match(
        make_opportunity(
            quality_requirements=[
                {
                    "maximum_ra_um": "1.6000",
                    "requirement_strength": "PREFERRED",
                }
            ]
        ),
        profile,
    )
    ra = atom(result, MatchDimension.QUALITY_REQUIREMENTS, "maximum_ra_um")
    assert ra.state == AtomicMatchState.UNKNOWN
    assert ra.reason_code == "PROFILE_QUALITY_UNIT_NOT_DECLARED"


def test_cmm_is_unknown_when_quality_fact_is_missing():
    result = match(
        make_opportunity(
            quality_requirements=[
                {"cmm_required": True, "requirement_strength": "PREFERRED"}
            ]
        )
    )
    cmm = atom(result, MatchDimension.QUALITY_REQUIREMENTS, "cmm_required")
    assert cmm.state == AtomicMatchState.UNKNOWN
    assert cmm.reason_code == "AMBIGUOUS_CMM_CAPABILITY_MAPPING"


def test_missing_current_certificate_is_unknown_not_mismatch():
    result = match(
        make_opportunity(
            required_certificates=[
                {
                    "certificate_type_code": "PNC_CERT_ISO9001",
                    "requirement_strength": "MANDATORY",
                }
            ]
        ),
        make_profile(
            certificates=(
                CertificateSnapshot(
                    certificate_id=1,
                    certificate_type_code="PNC_CERT_ISO9001",
                    issue_date=date(2025, 1, 1),
                    expiry_date=date(2025, 12, 31),
                ),
            )
        ),
    )
    current = atom(
        result,
        MatchDimension.REQUIRED_CERTIFICATES,
        "certificate_type_currently_valid",
    )
    assert current.state == AtomicMatchState.UNKNOWN
    assert current.reason_code == "PROFILE_CURRENT_CERTIFICATE_NOT_PROVEN"


def test_fingerprint_changes_when_relevant_opportunity_profile_or_date_changes():
    opportunity = make_opportunity(product_type_codes=["ASSEMBLY_UNIT"])
    first = match(opportunity, make_profile())
    changed_profile = match(
        opportunity,
        make_profile(
            products=(
                ProductExperienceSnapshot(
                    product_id=1,
                    product_type_code="ASSEMBLY_UNIT",
                ),
            )
        ),
    )
    changed_opportunity = match(
        make_opportunity(product_type_codes=["STANDARD_PARTS"]),
        make_profile(),
    )
    changed_date = ProcurementMatchingEngine().match(
        opportunity_id=11,
        opportunity=opportunity,
        profile=make_profile(),
        context=MatchEvaluationContext(evaluation_date=date(2026, 9, 4)),
    )

    assert (
        len(
            {
                first.input_fingerprint,
                changed_profile.input_fingerprint,
                changed_opportunity.input_fingerprint,
                changed_date.input_fingerprint,
            }
        )
        == 4
    )


def test_bundled_fifty_record_fixture_matches_without_false_hard_rejects():
    document = load_bundled_document()
    profile = make_profile()

    results = [
        ProcurementMatchingEngine().match(
            opportunity_id=index,
            opportunity=opportunity,
            profile=profile,
            context=MatchEvaluationContext(evaluation_date=EVALUATION_DATE),
        )
        for index, opportunity in enumerate(document.opportunities, start=1)
    ]

    assert len(results) == 50
    assert all(len(result.dimensions) == 8 for result in results)
    assert all(
        result.verdict != PairMatchVerdict.HARD_INCOMPATIBLE for result in results
    )


def test_multi_value_product_type_ambiguity_forces_undetermined_verdict():
    result = match(
        make_opportunity(product_type_codes=["ASSEMBLY_UNIT", "STANDARD_PARTS"]),
        make_profile(
            products=(
                ProductExperienceSnapshot(
                    product_id=1,
                    product_type_code="ASSEMBLY_UNIT",
                ),
            )
        ),
    )
    dim = dimension(result, MatchDimension.PRODUCT_TYPE_CODES)
    grouping = atom(result, MatchDimension.PRODUCT_TYPE_CODES, "grouping")
    assert grouping.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING"
    match_atom = atom(result, MatchDimension.PRODUCT_TYPE_CODES, "product_type_code")
    assert match_atom.state == AtomicMatchState.MATCH
    mismatch_atoms = [
        a for a in dim.atoms if a.subfield == "product_type_code"
        and a.state == AtomicMatchState.MISMATCH
    ]
    assert len(mismatch_atoms) == 1
    assert dim.state == DimensionMatchState.PARTIAL
    assert result.verdict == PairMatchVerdict.UNDETERMINED


def test_multi_value_okpd2_ambiguity_forces_undetermined_verdict():
    result = match(
        make_opportunity(okpd2_codes=["25.62.10.000", "25.62.20.000"]),
    )
    dim = dimension(result, MatchDimension.OKPD2_CODES)
    grouping = atom(result, MatchDimension.OKPD2_CODES, "grouping")
    assert grouping.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING"
    code_atoms = [
        a for a in dim.atoms if a.subfield == "code"
    ]
    assert len(code_atoms) == 2
    assert all(
        a.reason_code == "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING"
        for a in code_atoms
    )
    assert dim.state == DimensionMatchState.UNKNOWN
    assert result.verdict == PairMatchVerdict.UNDETERMINED


def test_single_value_product_type_preserves_existing_behavior():
    result = match(
        make_opportunity(product_type_codes=["ASSEMBLY_UNIT"]),
        make_profile(
            products=(
                ProductExperienceSnapshot(
                    product_id=1,
                    product_type_code="ASSEMBLY_UNIT",
                ),
            )
        ),
    )
    dim = dimension(result, MatchDimension.PRODUCT_TYPE_CODES)
    grouping_atoms = [
        a for a in dim.atoms if a.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING"
    ]
    assert grouping_atoms == []
    assert dim.state == DimensionMatchState.MATCH
    assert result.verdict == PairMatchVerdict.DETERMINATE_MATCH


def test_single_value_okpd2_preserves_existing_behavior():
    result = match(
        make_opportunity(okpd2_codes=["25.62.10.000"]),
    )
    dim = dimension(result, MatchDimension.OKPD2_CODES)
    grouping_atoms = [
        a for a in dim.atoms if a.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING"
    ]
    assert grouping_atoms == []
    assert dim.state == DimensionMatchState.UNKNOWN
    okpd_atom = atom(result, MatchDimension.OKPD2_CODES, "code")
    assert okpd_atom.reason_code == "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING"


@pytest.mark.parametrize("invalid_grade", [-1, 0, 19, -100, 100])
def test_invalid_min_it_grade_rejected_at_schema_boundary(invalid_grade: int):
    with pytest.raises(ValidationError, match="min_it_grade"):
        QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=invalid_grade,
            measuring_tools=False,
            cim_machine=False,
        )


@pytest.mark.parametrize("valid_grade", [1, 8, 18])
def test_valid_min_it_grade_accepted(valid_grade: int):
    snapshot = QualityCapabilitySnapshot(
        capability_id=1,
        min_it_grade=valid_grade,
        measuring_tools=False,
        cim_machine=False,
    )
    assert snapshot.min_it_grade == valid_grade


def test_negative_equipment_dimensions_rejected():
    with pytest.raises(ValidationError, match="positive"):
        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            working_zone_x=Decimal("-100"),
        )


def test_negative_max_diameter_rejected():
    with pytest.raises(ValidationError, match="positive"):
        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            max_diameter=Decimal("-50"),
        )


def test_zero_equipment_dimension_rejected():
    with pytest.raises(ValidationError, match="positive"):
        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            working_zone_y=Decimal("0"),
        )


def test_negative_min_ra_rejected():
    with pytest.raises(ValidationError, match="positive"):
        QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=7,
            min_ra=Decimal("-0.8"),
            measuring_tools=False,
            cim_machine=False,
        )


def test_zero_min_ra_rejected():
    with pytest.raises(ValidationError, match="positive"):
        QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=7,
            min_ra=Decimal("0"),
            measuring_tools=False,
            cim_machine=False,
        )


def test_invalid_profile_numeric_facts_cannot_reach_engine():
    with pytest.raises(ValidationError):
        QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=-1,
            measuring_tools=False,
            cim_machine=False,
        )
    with pytest.raises(ValidationError):
        EquipmentSnapshot(
            equipment_id=1,
            equipment_type_code="TURNING",
            cnc=False,
            quantity=1,
            working_zone_x=Decimal("-100"),
        )
    with pytest.raises(ValidationError):
        QualityCapabilitySnapshot(
            capability_id=1,
            min_it_grade=7,
            min_ra=Decimal("-1.6"),
            measuring_tools=False,
            cim_machine=False,
        )
