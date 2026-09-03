from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.procurement_matching import (
    MATCH_RULESET_VERSION,
    MatchResult,
    OpportunityMatchIdentity,
)
from app.schemas.procurement_opportunities import Deadline

MATCH_SCORING_VERSION = "procurement-profile-score-v1"


class MatchingCriterion(StrEnum):
    PRODUCT_EXPERIENCE = "product_experience"
    MATERIAL_CAPABILITY = "material_capability"
    TECHNOLOGY_CAPABILITY = "technology_capability"
    EQUIPMENT_CAPABILITY = "equipment_capability"
    DIMENSIONS_MASS = "dimensions_mass"
    QUANTITY_CAPACITY = "quantity_capacity"
    EXECUTION_DEADLINE = "execution_deadline"
    REGION_LOGISTICS = "region_logistics"
    CERTIFICATES = "certificates"
    QUALITY_CAPABILITY = "quality_capability"


CRITERION_ORDER: tuple[MatchingCriterion, ...] = tuple(MatchingCriterion)
CRITERION_WEIGHTS: dict[MatchingCriterion, int] = {
    MatchingCriterion.PRODUCT_EXPERIENCE: 8,
    MatchingCriterion.MATERIAL_CAPABILITY: 23,
    MatchingCriterion.TECHNOLOGY_CAPABILITY: 23,
    MatchingCriterion.EQUIPMENT_CAPABILITY: 15,
    MatchingCriterion.DIMENSIONS_MASS: 12,
    MatchingCriterion.QUANTITY_CAPACITY: 5,
    MatchingCriterion.EXECUTION_DEADLINE: 5,
    MatchingCriterion.REGION_LOGISTICS: 3,
    MatchingCriterion.CERTIFICATES: 3,
    MatchingCriterion.QUALITY_CAPABILITY: 3,
}
assert sum(CRITERION_WEIGHTS.values()) == 100

CAPABILITY_CRITERIA = frozenset(
    {
        MatchingCriterion.MATERIAL_CAPABILITY,
        MatchingCriterion.TECHNOLOGY_CAPABILITY,
        MatchingCriterion.EQUIPMENT_CAPABILITY,
        MatchingCriterion.DIMENSIONS_MASS,
        MatchingCriterion.QUALITY_CAPABILITY,
    }
)


class CriterionValue(StrEnum):
    FULL = "1.0"
    PARTIAL = "0.5"
    ZERO = "0.0"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    @property
    def numeric(self) -> Decimal | None:
        if self in {self.UNKNOWN, self.NOT_APPLICABLE}:
            return None
        return Decimal(self.value)


KNOWN_APPLICABLE_VALUES = frozenset(
    {CriterionValue.FULL, CriterionValue.PARTIAL, CriterionValue.ZERO}
)


class MatchStatus(StrEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    POTENTIAL = "POTENTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOW_MATCH = "LOW_MATCH"
    MATCH = "MATCH"


class ExplanationCriterion(StrEnum):
    MARKET_ELIGIBILITY = "market_eligibility"
    PRODUCT_EXPERIENCE = MatchingCriterion.PRODUCT_EXPERIENCE.value
    MATERIAL_CAPABILITY = MatchingCriterion.MATERIAL_CAPABILITY.value
    TECHNOLOGY_CAPABILITY = MatchingCriterion.TECHNOLOGY_CAPABILITY.value
    EQUIPMENT_CAPABILITY = MatchingCriterion.EQUIPMENT_CAPABILITY.value
    DIMENSIONS_MASS = MatchingCriterion.DIMENSIONS_MASS.value
    QUANTITY_CAPACITY = MatchingCriterion.QUANTITY_CAPACITY.value
    EXECUTION_DEADLINE = MatchingCriterion.EXECUTION_DEADLINE.value
    REGION_LOGISTICS = MatchingCriterion.REGION_LOGISTICS.value
    CERTIFICATES = MatchingCriterion.CERTIFICATES.value
    QUALITY_CAPABILITY = MatchingCriterion.QUALITY_CAPABILITY.value


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RankingEvaluationContext(_FrozenModel):
    evaluation_time: datetime
    ruleset_version: str = MATCH_RULESET_VERSION
    scoring_version: str = MATCH_SCORING_VERSION

    @field_validator("evaluation_time")
    @classmethod
    def require_explicit_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluation_time must include a timezone offset.")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_versions(self) -> Self:
        if self.ruleset_version != MATCH_RULESET_VERSION:
            raise ValueError("Unsupported procurement matching ruleset version.")
        if self.scoring_version != MATCH_SCORING_VERSION:
            raise ValueError("Unsupported procurement scoring version.")
        return self


class CriterionTrace(_FrozenModel):
    criterion: MatchingCriterion
    weight: int = Field(gt=0)
    value: CriterionValue
    evaluated_fraction: Decimal = Field(ge=0, le=1)
    mandatory: bool = False
    remediable: bool = False
    evidence_ids: tuple[str, ...] = ()
    unresolved_evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        if self.weight != CRITERION_WEIGHTS[self.criterion]:
            raise ValueError("Criterion weight does not match the V1 baseline.")
        if self.remediable and self.value != CriterionValue.PARTIAL:
            raise ValueError("A remediable criterion must have value 0.5.")
        if self.value in {CriterionValue.UNKNOWN, CriterionValue.NOT_APPLICABLE}:
            if self.evaluated_fraction != 0:
                raise ValueError(
                    "UNKNOWN and NOT_APPLICABLE must have zero evaluated fraction."
                )
        elif self.evaluated_fraction <= 0:
            raise ValueError("A numeric criterion requires an evaluated fraction.")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Criterion evidence IDs must be unique.")
        if len(self.unresolved_evidence_ids) != len(set(self.unresolved_evidence_ids)):
            raise ValueError("Unresolved evidence IDs must be unique.")
        if not set(self.unresolved_evidence_ids).issubset(self.evidence_ids):
            raise ValueError("Unresolved evidence must belong to the criterion.")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ValueError("Criterion reason codes must be sorted and unique.")
        return self


class MatchExplanation(_FrozenModel):
    criterion: ExplanationCriterion
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


class MatchScoreSummary(_FrozenModel):
    compatibility_score: Decimal | None = Field(default=None, ge=0, le=100)
    coverage: Decimal = Field(ge=0, le=1)
    ranking_score: Decimal = Field(ge=0, le=100)


class ScoredMatchResult(_FrozenModel):
    opportunity_id: int = Field(gt=0)
    opportunity_identity: OpportunityMatchIdentity
    profile_id: int = Field(gt=0)
    ruleset_version: str = MATCH_RULESET_VERSION
    scoring_version: str = MATCH_SCORING_VERSION
    evaluation_time: datetime
    application_deadline: Deadline = None
    match_status: MatchStatus
    compatibility_score: Decimal | None = Field(default=None, ge=0, le=100)
    coverage: Decimal = Field(ge=0, le=1)
    ranking_score: Decimal = Field(ge=0, le=100)
    eligibility_reasons: tuple[MatchExplanation, ...] = ()
    positive_reasons: tuple[MatchExplanation, ...] = ()
    hard_conflicts: tuple[MatchExplanation, ...] = ()
    remediable_limitations: tuple[MatchExplanation, ...] = ()
    missing_data: tuple[MatchExplanation, ...] = ()
    missing_capabilities: tuple[MatchExplanation, ...] = ()
    trace: tuple[CriterionTrace, ...] = Field(
        min_length=len(CRITERION_ORDER),
        max_length=len(CRITERION_ORDER),
    )
    slice_a_result: MatchResult

    @field_validator("evaluation_time")
    @classmethod
    def require_explicit_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluation_time must include a timezone offset.")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_result_contract(self) -> Self:
        if self.ruleset_version != MATCH_RULESET_VERSION:
            raise ValueError("Unsupported procurement matching ruleset version.")
        if self.scoring_version != MATCH_SCORING_VERSION:
            raise ValueError("Unsupported procurement scoring version.")
        if tuple(item.criterion for item in self.trace) != CRITERION_ORDER:
            raise ValueError("Trace must use the fixed Slice B criterion order.")
        if self.opportunity_id != self.slice_a_result.opportunity_id:
            raise ValueError("Slice A and Slice B opportunity IDs must match.")
        if self.opportunity_identity != self.slice_a_result.opportunity_identity:
            raise ValueError("Slice A and Slice B opportunity identities must match.")
        if self.profile_id != self.slice_a_result.profile_id:
            raise ValueError("Slice A and Slice B profile IDs must match.")
        if self.ruleset_version != self.slice_a_result.ruleset_version:
            raise ValueError("Slice A and Slice B ruleset versions must match.")
        if self.evaluation_time.date() != self.slice_a_result.evaluation_date:
            raise ValueError(
                "Slice A evaluation date must derive from evaluation_time."
            )
        return self
