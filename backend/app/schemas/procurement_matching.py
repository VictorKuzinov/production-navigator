from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.procurement_opportunities import RequirementStrength
from app.models.profile_capabilities import CapabilityState, ProfileSectionState

MATCH_RULESET_VERSION = "procurement-profile-match-v1"


class MatchDimension(StrEnum):
    OKPD2_CODES = "okpd2_codes"
    PRODUCT_TYPE_CODES = "product_type_codes"
    MATERIAL_REQUIREMENTS = "material_requirements"
    TECHNOLOGY_REQUIREMENTS = "technology_requirements"
    EQUIPMENT_REQUIREMENTS = "equipment_requirements"
    DIMENSIONAL_MASS_REQUIREMENTS = "dimensional_mass_requirements"
    QUALITY_REQUIREMENTS = "quality_requirements"
    REQUIRED_CERTIFICATES = "required_certificates"


MATCH_DIMENSION_ORDER: tuple[MatchDimension, ...] = tuple(MatchDimension)


class AtomicMatchState(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DimensionMatchState(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MatchSeverity(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PairMatchVerdict(StrEnum):
    DETERMINATE_MATCH = "DETERMINATE_MATCH"
    HARD_INCOMPATIBLE = "HARD_INCOMPATIBLE"
    UNDETERMINED = "UNDETERMINED"


class UnknownOrigin(StrEnum):
    PROCUREMENT_SOURCE = "PROCUREMENT_SOURCE"
    ENTERPRISE_PROFILE = "ENTERPRISE_PROFILE"
    MISSING_PROFILE_CAPABILITY = "MISSING_PROFILE_CAPABILITY"
    AMBIGUOUS_DOMAIN_SEMANTICS = "AMBIGUOUS_DOMAIN_SEMANTICS"
    DATA_INTEGRITY = "DATA_INTEGRITY"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MatchFact(_FrozenModel):
    path: str = Field(min_length=1)
    value: str | int | bool | Decimal | date | None


class MatchAtomResult(_FrozenModel):
    evidence_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    dimension: MatchDimension
    target_key: str = Field(min_length=1)
    subfield: str = Field(min_length=1)
    requirement_path: str = Field(min_length=1)
    requirement: MatchFact
    capability_path: str | None = None
    capability: MatchFact | None = None
    state: AtomicMatchState
    severity: MatchSeverity
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    reason: str = Field(min_length=1)
    origin: UnknownOrigin | None = None
    resolution_path: tuple[str, ...] = ()
    requirement_strength: RequirementStrength | None = None

    @model_validator(mode="after")
    def validate_state_contract(self) -> Self:
        if self.requirement.path != self.requirement_path:
            raise ValueError("requirement fact path must match requirement_path.")
        if self.capability is not None:
            if self.capability_path is None:
                raise ValueError("capability fact requires capability_path.")
            if self.capability.path != self.capability_path:
                raise ValueError("capability fact path must match capability_path.")
        elif self.capability_path is not None:
            raise ValueError("capability_path requires a capability fact.")

        if self.state == AtomicMatchState.UNKNOWN:
            if self.severity != MatchSeverity.UNRESOLVED or self.origin is None:
                raise ValueError("UNKNOWN requires UNRESOLVED severity and origin.")
        elif self.origin is not None:
            raise ValueError("Only UNKNOWN atoms may declare an origin.")

        if self.state == AtomicMatchState.NOT_APPLICABLE:
            if self.severity != MatchSeverity.NOT_APPLICABLE:
                raise ValueError(
                    "NOT_APPLICABLE state requires NOT_APPLICABLE severity."
                )
        elif self.severity == MatchSeverity.NOT_APPLICABLE:
            raise ValueError("NOT_APPLICABLE severity requires NOT_APPLICABLE state.")

        if self.severity == MatchSeverity.HARD:
            if self.state != AtomicMatchState.MISMATCH:
                raise ValueError("HARD severity is valid only for MISMATCH.")
            hard_dimensions = {
                "HARD_MATERIAL_EXPLICIT_UNSUPPORTED": (
                    MatchDimension.MATERIAL_REQUIREMENTS
                ),
                "HARD_TECHNOLOGY_EXPLICIT_UNSUPPORTED": (
                    MatchDimension.TECHNOLOGY_REQUIREMENTS
                ),
            }
            if self.reason_code not in hard_dimensions:
                raise ValueError("The reason code is not an active Slice A hard rule.")
            if self.dimension != hard_dimensions[self.reason_code]:
                raise ValueError("The hard reason is invalid for this dimension.")
            if self.requirement_strength != RequirementStrength.MANDATORY:
                raise ValueError("HARD evidence requires a MANDATORY requirement.")
        return self


class MatchDimensionResult(_FrozenModel):
    dimension: MatchDimension
    state: DimensionMatchState
    atoms: tuple[MatchAtomResult, ...] = Field(min_length=1)
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_atoms(self) -> Self:
        if any(atom.dimension != self.dimension for atom in self.atoms):
            raise ValueError("Every atom must belong to its containing dimension.")
        evidence_ids = [atom.evidence_id for atom in self.atoms]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique within a dimension.")
        expected_reasons = tuple(sorted({atom.reason_code for atom in self.atoms}))
        if self.reason_codes != expected_reasons:
            raise ValueError("reason_codes must be sorted and deduplicated.")
        return self


class OpportunityMatchIdentity(_FrozenModel):
    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)


class MatchEvaluationContext(_FrozenModel):
    evaluation_date: date
    ruleset_version: str = MATCH_RULESET_VERSION

    @model_validator(mode="after")
    def validate_ruleset(self) -> Self:
        if self.ruleset_version != MATCH_RULESET_VERSION:
            raise ValueError("Unsupported procurement matching ruleset version.")
        return self


class ProductExperienceSnapshot(_FrozenModel):
    product_id: int = Field(gt=0)
    product_type_code: str = Field(min_length=1)


class TechnologyCapabilitySnapshot(_FrozenModel):
    capability_id: int = Field(gt=0)
    technology_code: str = Field(min_length=1)
    state: CapabilityState


class MaterialCapabilitySnapshot(_FrozenModel):
    capability_id: int = Field(gt=0)
    material_group_code: str | None = None
    material_id: int | None = Field(default=None, gt=0)
    state: CapabilityState

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if (self.material_group_code is None) == (self.material_id is None):
            raise ValueError("Material capability requires exactly one target.")
        return self


class EquipmentSnapshot(_FrozenModel):
    equipment_id: int = Field(gt=0)
    equipment_type_code: str = Field(min_length=1)
    cnc: bool
    axes: int | None = Field(default=None, ge=1)
    quantity: int = Field(ge=1)
    max_diameter: Decimal | None = None
    working_zone_x: Decimal | None = None
    working_zone_y: Decimal | None = None
    working_zone_z: Decimal | None = None

    @model_validator(mode="after")
    def validate_finite_values(self) -> Self:
        values = (
            self.max_diameter,
            self.working_zone_x,
            self.working_zone_y,
            self.working_zone_z,
        )
        for value in values:
            if value is not None:
                if not value.is_finite():
                    raise ValueError("Equipment numeric facts must be finite.")
                if value <= 0:
                    raise ValueError(
                        "Equipment dimensional facts must be positive."
                    )
        return self


class QualityCapabilitySnapshot(_FrozenModel):
    capability_id: int = Field(gt=0)
    min_it_grade: int | None = Field(default=None, ge=1, le=18)
    min_ra: Decimal | None = None
    measuring_tools: bool
    cim_machine: bool

    @model_validator(mode="after")
    def validate_finite_values(self) -> Self:
        if self.min_ra is not None:
            if not self.min_ra.is_finite():
                raise ValueError("Quality numeric facts must be finite.")
            if self.min_ra <= 0:
                raise ValueError("Quality min_ra must be positive.")
        return self


class CertificateSnapshot(_FrozenModel):
    certificate_id: int = Field(gt=0)
    certificate_type_code: str = Field(min_length=1)
    issue_date: date
    expiry_date: date


class ProfileMatchingSnapshot(_FrozenModel):
    profile_id: int = Field(gt=0)
    products: tuple[ProductExperienceSnapshot, ...] = ()
    technology_capabilities: tuple[TechnologyCapabilitySnapshot, ...] = ()
    material_capabilities: tuple[MaterialCapabilitySnapshot, ...] = ()
    technology_section_state: ProfileSectionState
    material_section_state: ProfileSectionState
    equipments: tuple[EquipmentSnapshot, ...] = ()
    quality_capability: QualityCapabilitySnapshot | None = None
    certificates: tuple[CertificateSnapshot, ...] = ()

    @model_validator(mode="after")
    def validate_projection_identity(self) -> Self:
        unique_sets = (
            ("product IDs", [item.product_id for item in self.products]),
            (
                "technology targets",
                [item.technology_code for item in self.technology_capabilities],
            ),
            (
                "material targets",
                [
                    ("group", item.material_group_code)
                    if item.material_group_code is not None
                    else ("material", item.material_id)
                    for item in self.material_capabilities
                ],
            ),
            ("equipment IDs", [item.equipment_id for item in self.equipments]),
            (
                "certificate IDs",
                [item.certificate_id for item in self.certificates],
            ),
        )
        for label, values in unique_sets:
            if len(values) != len(set(values)):
                raise ValueError(f"Profile matching projection has duplicate {label}.")
        return self


class MatchResult(_FrozenModel):
    opportunity_id: int = Field(gt=0)
    opportunity_identity: OpportunityMatchIdentity
    profile_id: int = Field(gt=0)
    ruleset_version: str = MATCH_RULESET_VERSION
    evaluation_date: date
    input_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    verdict: PairMatchVerdict
    dimensions: tuple[MatchDimensionResult, ...] = Field(
        min_length=len(MATCH_DIMENSION_ORDER),
        max_length=len(MATCH_DIMENSION_ORDER),
    )
    hard_incompatibility_evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_result_contract(self) -> Self:
        if self.ruleset_version != MATCH_RULESET_VERSION:
            raise ValueError("Unsupported procurement matching ruleset version.")
        if tuple(item.dimension for item in self.dimensions) != MATCH_DIMENSION_ORDER:
            raise ValueError("Dimensions must use the fixed Slice A order.")
        atoms = [atom for dimension in self.dimensions for atom in dimension.atoms]
        evidence_ids = [atom.evidence_id for atom in atoms]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique across MatchResult.")
        hard_ids = tuple(
            sorted(
                atom.evidence_id
                for atom in atoms
                if atom.severity == MatchSeverity.HARD
            )
        )
        if self.hard_incompatibility_evidence_ids != hard_ids:
            raise ValueError("Hard incompatibility IDs must match HARD atoms.")
        if bool(hard_ids) != (self.verdict == PairMatchVerdict.HARD_INCOMPATIBLE):
            raise ValueError("Pair verdict must reflect hard incompatibilities.")
        return self
