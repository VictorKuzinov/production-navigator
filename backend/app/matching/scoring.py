import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.procurement_opportunities import (
    ProcurementOpportunityStatus,
    RequirementStrength,
)
from app.schemas.procurement_matching import (
    AtomicMatchState,
    MatchAtomResult,
    MatchDimension,
    MatchResult,
    MatchSeverity,
    UnknownOrigin,
)
from app.schemas.procurement_matching_scoring import (
    CAPABILITY_CRITERIA,
    CRITERION_ORDER,
    CRITERION_WEIGHTS,
    KNOWN_APPLICABLE_VALUES,
    CriterionTrace,
    CriterionValue,
    ExplanationCriterion,
    MatchExplanation,
    MatchingCriterion,
    MatchScoreSummary,
    MatchStatus,
    RankingEvaluationContext,
    ScoredMatchResult,
)
from app.schemas.procurement_opportunities import (
    Deadline,
    PreparedOpportunityInput,
    canonicalize_opportunity,
)

_DIMENSION_CRITERIA: dict[MatchDimension, MatchingCriterion] = {
    MatchDimension.PRODUCT_TYPE_CODES: MatchingCriterion.PRODUCT_EXPERIENCE,
    MatchDimension.MATERIAL_REQUIREMENTS: MatchingCriterion.MATERIAL_CAPABILITY,
    MatchDimension.TECHNOLOGY_REQUIREMENTS: (MatchingCriterion.TECHNOLOGY_CAPABILITY),
    MatchDimension.EQUIPMENT_REQUIREMENTS: MatchingCriterion.EQUIPMENT_CAPABILITY,
    MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS: MatchingCriterion.DIMENSIONS_MASS,
    MatchDimension.REQUIRED_CERTIFICATES: MatchingCriterion.CERTIFICATES,
    MatchDimension.QUALITY_REQUIREMENTS: MatchingCriterion.QUALITY_CAPABILITY,
}

# These Slice A dimensions expose independently checkable subfields. An unresolved
# PREFERRED subfield may therefore remain uncovered while determinate siblings are
# scored. Collection/grouping ambiguity and every unresolved MANDATORY subfield
# still block the whole criterion.
_INDEPENDENT_PREFERRED_SUBATOM_CRITERIA = frozenset(
    {
        MatchingCriterion.EQUIPMENT_CAPABILITY,
        MatchingCriterion.DIMENSIONS_MASS,
        MatchingCriterion.CERTIFICATES,
        MatchingCriterion.QUALITY_CAPABILITY,
    }
)

_GENERATED_UNKNOWN_REASONS: dict[MatchingCriterion, tuple[str, str]] = {
    MatchingCriterion.QUANTITY_CAPACITY: (
        "COMPARABLE_CAPACITY_NOT_AVAILABLE",
        "The profile has no approved comparable production-capacity fact.",
    ),
    MatchingCriterion.EXECUTION_DEADLINE: (
        "EARLIEST_FEASIBLE_COMPLETION_NOT_AVAILABLE",
        "The profile has no approved earliest feasible completion fact.",
    ),
    MatchingCriterion.REGION_LOGISTICS: (
        "PROFILE_LOGISTICS_CAPABILITY_NOT_AVAILABLE",
        "The profile has no approved logistics capability for region comparison.",
    ),
}

_MARKET_STATUSES = {
    ProcurementOpportunityStatus.CLOSED,
    ProcurementOpportunityStatus.CANCELLED,
    ProcurementOpportunityStatus.AWARDED,
}

_ONE_HUNDRED = Decimal(100)
_COMPATIBILITY_FACTOR = Decimal("0.85")
_COVERAGE_FACTOR = Decimal("0.15")
_MINIMUM_COVERAGE = Decimal("0.35")
_MATCH_COVERAGE = Decimal("0.60")
_LOW_MATCH_SCORE = Decimal(50)
_MATCH_SCORE = Decimal(75)


def calculate_scores(trace: Sequence[CriterionTrace]) -> MatchScoreSummary:
    """Apply the exact Slice B compatibility, coverage, and ranking formulas."""
    known = [item for item in trace if item.value in KNOWN_APPLICABLE_VALUES]
    expected = [item for item in trace if item.value != CriterionValue.NOT_APPLICABLE]
    known_weight = sum(
        (Decimal(item.weight) * item.evaluated_fraction for item in known),
        Decimal(0),
    )
    expected_weight = sum((Decimal(item.weight) for item in expected), Decimal(0))

    compatibility = None
    if known_weight:
        weighted_value = sum(
            (
                Decimal(item.weight)
                * item.evaluated_fraction
                * (item.value.numeric or Decimal(0))
                for item in known
            ),
            Decimal(0),
        )
        compatibility = _ONE_HUNDRED * weighted_value / known_weight

    coverage = known_weight / expected_weight if expected_weight else Decimal(0)
    ranking = (
        _COMPATIBILITY_FACTOR * compatibility
        + _COVERAGE_FACTOR * (_ONE_HUNDRED * coverage)
        if compatibility is not None
        else Decimal(0)
    )
    return MatchScoreSummary(
        compatibility_score=compatibility,
        coverage=coverage,
        ranking_score=ranking,
    )


def determine_match_status(
    trace: Sequence[CriterionTrace],
    scores: MatchScoreSummary,
    *,
    market_unavailable: bool,
    has_hard_conflict: bool,
) -> MatchStatus:
    """Apply the binding status rules in their declared first-match order."""
    if market_unavailable:
        return MatchStatus.NOT_ELIGIBLE
    if has_hard_conflict:
        return MatchStatus.INCOMPATIBLE
    if any(item.mandatory and item.remediable for item in trace):
        return MatchStatus.POTENTIAL
    evaluated_capability = any(
        item.criterion in CAPABILITY_CRITERIA
        and item.value in KNOWN_APPLICABLE_VALUES
        and item.evaluated_fraction > 0
        for item in trace
    )
    if scores.coverage < _MINIMUM_COVERAGE or not evaluated_capability:
        return MatchStatus.INSUFFICIENT_DATA
    if (
        scores.compatibility_score is not None
        and scores.compatibility_score < _LOW_MATCH_SCORE
    ):
        return MatchStatus.LOW_MATCH
    if (
        scores.compatibility_score is None
        or scores.compatibility_score < _MATCH_SCORE
        or scores.coverage < _MATCH_COVERAGE
    ):
        return MatchStatus.POTENTIAL
    return MatchStatus.MATCH


class ProcurementMatchingScoringEngine:
    """Pure deterministic Slice B scoring over one Slice A result."""

    def score(
        self,
        opportunity: PreparedOpportunityInput,
        match_result: MatchResult,
        context: RankingEvaluationContext,
    ) -> ScoredMatchResult:
        opportunity = canonicalize_opportunity(opportunity)
        self._validate_inputs(opportunity, match_result, context)
        trace = self._criterion_trace(opportunity, match_result)
        scores = calculate_scores(trace)
        eligibility = self._eligibility_reasons(opportunity, context)
        hard_conflicts = self._hard_conflicts(match_result)
        status = determine_match_status(
            trace,
            scores,
            market_unavailable=bool(eligibility),
            has_hard_conflict=bool(hard_conflicts),
        )
        return ScoredMatchResult(
            opportunity_id=match_result.opportunity_id,
            opportunity_identity=match_result.opportunity_identity,
            profile_id=match_result.profile_id,
            ruleset_version=context.ruleset_version,
            scoring_version=context.scoring_version,
            evaluation_time=context.evaluation_time,
            application_deadline=opportunity.application_deadline,
            match_status=status,
            compatibility_score=scores.compatibility_score,
            coverage=scores.coverage,
            ranking_score=scores.ranking_score,
            eligibility_reasons=eligibility,
            positive_reasons=self._positive_reasons(match_result),
            hard_conflicts=hard_conflicts,
            remediable_limitations=self._remediable_limitations(trace),
            missing_data=self._missing_reasons(
                opportunity,
                match_result,
                trace,
                capabilities=False,
            ),
            missing_capabilities=self._missing_reasons(
                opportunity,
                match_result,
                trace,
                capabilities=True,
            ),
            trace=trace,
            slice_a_result=match_result,
        )

    @staticmethod
    def _validate_inputs(
        opportunity: PreparedOpportunityInput,
        match_result: MatchResult,
        context: RankingEvaluationContext,
    ) -> None:
        identity = match_result.opportunity_identity
        if (opportunity.source, opportunity.external_id) != (
            identity.source,
            identity.external_id,
        ):
            raise ValueError("Opportunity identity does not match the Slice A result.")
        if match_result.ruleset_version != context.ruleset_version:
            raise ValueError("Slice A and Slice B ruleset versions do not match.")
        if match_result.evaluation_date != context.evaluation_time.date():
            raise ValueError(
                "Slice A evaluation date must derive from evaluation_time."
            )

    def _criterion_trace(
        self,
        opportunity: PreparedOpportunityInput,
        match_result: MatchResult,
    ) -> tuple[CriterionTrace, ...]:
        dimensions = {item.dimension: item for item in match_result.dimensions}
        by_criterion = {
            criterion: self._dimension_trace(criterion, dimensions[dimension].atoms)
            for dimension, criterion in _DIMENSION_CRITERIA.items()
        }
        by_criterion[MatchingCriterion.QUANTITY_CAPACITY] = self._unknown_trace(
            opportunity,
            MatchingCriterion.QUANTITY_CAPACITY,
        )
        by_criterion[MatchingCriterion.EXECUTION_DEADLINE] = self._unknown_trace(
            opportunity,
            MatchingCriterion.EXECUTION_DEADLINE,
        )
        by_criterion[MatchingCriterion.REGION_LOGISTICS] = self._unknown_trace(
            opportunity,
            MatchingCriterion.REGION_LOGISTICS,
        )
        return tuple(by_criterion[criterion] for criterion in CRITERION_ORDER)

    @staticmethod
    def _dimension_trace(
        criterion: MatchingCriterion,
        atoms: Sequence[MatchAtomResult],
    ) -> CriterionTrace:
        applicable = [
            atom for atom in atoms if atom.state != AtomicMatchState.NOT_APPLICABLE
        ]
        unresolved = [
            atom for atom in applicable if atom.state == AtomicMatchState.UNKNOWN
        ]
        determinate = [
            atom
            for atom in applicable
            if atom.state in {AtomicMatchState.MATCH, AtomicMatchState.MISMATCH}
        ]
        preferred_subatoms_are_independent = (
            criterion in _INDEPENDENT_PREFERRED_SUBATOM_CRITERIA
        )
        blocking_unknown = any(
            not preferred_subatoms_are_independent
            or atom.requirement_strength != RequirementStrength.PREFERRED
            for atom in unresolved
        )
        if not applicable:
            value = CriterionValue.NOT_APPLICABLE
            evaluated_fraction = Decimal(0)
        elif blocking_unknown or not determinate:
            value = CriterionValue.UNKNOWN
            evaluated_fraction = Decimal(0)
        else:
            determinate_states = {atom.state for atom in determinate}
            if determinate_states == {AtomicMatchState.MATCH}:
                value = CriterionValue.FULL
            elif determinate_states == {AtomicMatchState.MISMATCH}:
                value = CriterionValue.ZERO
            else:
                value = CriterionValue.PARTIAL
            evaluated_fraction = Decimal(len(determinate)) / Decimal(len(applicable))
        return CriterionTrace(
            criterion=criterion,
            weight=CRITERION_WEIGHTS[criterion],
            value=value,
            evaluated_fraction=evaluated_fraction,
            mandatory=any(
                atom.requirement_strength == RequirementStrength.MANDATORY
                for atom in applicable
            ),
            remediable=False,
            evidence_ids=tuple(sorted(atom.evidence_id for atom in atoms)),
            unresolved_evidence_ids=tuple(
                sorted(atom.evidence_id for atom in unresolved)
            ),
            reason_codes=tuple(sorted({atom.reason_code for atom in atoms})),
        )

    @classmethod
    def _unknown_trace(
        cls,
        opportunity: PreparedOpportunityInput,
        criterion: MatchingCriterion,
    ) -> CriterionTrace:
        code, _ = cls._generated_unknown_reason(opportunity, criterion)
        evidence_id = cls._generated_evidence_id(opportunity, criterion, code)
        return CriterionTrace(
            criterion=criterion,
            weight=CRITERION_WEIGHTS[criterion],
            value=CriterionValue.UNKNOWN,
            evaluated_fraction=Decimal(0),
            evidence_ids=(evidence_id,),
            unresolved_evidence_ids=(evidence_id,),
            reason_codes=(code,),
        )

    @staticmethod
    def _generated_unknown_reason(
        opportunity: PreparedOpportunityInput,
        criterion: MatchingCriterion,
    ) -> tuple[str, str]:
        if (
            criterion == MatchingCriterion.REGION_LOGISTICS
            and opportunity.region_code is None
        ):
            return (
                "PROCUREMENT_REGION_NOT_DECLARED",
                "The procurement source did not declare a region requirement.",
            )
        return _GENERATED_UNKNOWN_REASONS[criterion]

    @staticmethod
    def _generated_evidence_id(
        opportunity: PreparedOpportunityInput,
        criterion: MatchingCriterion,
        code: str,
    ) -> str:
        encoded = json.dumps(
            {
                "source": opportunity.source,
                "external_id": opportunity.external_id,
                "criterion": criterion.value,
                "code": code,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _eligibility_reasons(
        cls,
        opportunity: PreparedOpportunityInput,
        context: RankingEvaluationContext,
    ) -> tuple[MatchExplanation, ...]:
        reasons: list[MatchExplanation] = []
        if opportunity.status in _MARKET_STATUSES:
            code = f"MARKET_STATUS_{opportunity.status.value}"
            reasons.append(
                MatchExplanation(
                    criterion=ExplanationCriterion.MARKET_ELIGIBILITY,
                    code=code,
                    message=(
                        "The procurement status proves that the opportunity is "
                        "not available to the market."
                    ),
                    evidence_ids=(
                        cls._generated_evidence_id(
                            opportunity,
                            MatchingCriterion.EXECUTION_DEADLINE,
                            code,
                        ),
                    ),
                )
            )
        if cls._deadline_expired(
            opportunity.application_deadline,
            context.evaluation_time,
        ):
            code = "APPLICATION_DEADLINE_EXPIRED"
            reasons.append(
                MatchExplanation(
                    criterion=ExplanationCriterion.MARKET_ELIGIBILITY,
                    code=code,
                    message=(
                        "The explicit application deadline is earlier than the "
                        "evaluation time."
                    ),
                    evidence_ids=(
                        cls._generated_evidence_id(
                            opportunity,
                            MatchingCriterion.EXECUTION_DEADLINE,
                            code,
                        ),
                    ),
                )
            )
        return tuple(sorted(reasons, key=lambda item: item.code))

    @staticmethod
    def _deadline_expired(deadline: Deadline, evaluation_time: datetime) -> bool:
        if isinstance(deadline, datetime):
            return deadline.astimezone(UTC) < evaluation_time.astimezone(UTC)
        if isinstance(deadline, date):
            return deadline < evaluation_time.date()
        return False

    @staticmethod
    def _atom_explanation(
        criterion: MatchingCriterion,
        atom: MatchAtomResult,
    ) -> MatchExplanation:
        return MatchExplanation(
            criterion=ExplanationCriterion(criterion.value),
            code=atom.reason_code,
            message=atom.reason,
            evidence_ids=(atom.evidence_id,),
        )

    @classmethod
    def _hard_conflicts(
        cls,
        match_result: MatchResult,
    ) -> tuple[MatchExplanation, ...]:
        return cls._atom_reasons(
            match_result,
            lambda atom: atom.severity == MatchSeverity.HARD,
        )

    @classmethod
    def _positive_reasons(
        cls,
        match_result: MatchResult,
    ) -> tuple[MatchExplanation, ...]:
        return cls._atom_reasons(
            match_result,
            lambda atom: atom.state == AtomicMatchState.MATCH,
        )

    @classmethod
    def _atom_reasons(
        cls,
        match_result: MatchResult,
        predicate,
    ) -> tuple[MatchExplanation, ...]:
        reasons: list[MatchExplanation] = []
        for dimension in match_result.dimensions:
            criterion = _DIMENSION_CRITERIA.get(dimension.dimension)
            if criterion is None:
                continue
            for atom in dimension.atoms:
                if predicate(atom):
                    reasons.append(cls._atom_explanation(criterion, atom))
        return tuple(
            sorted(
                reasons,
                key=lambda item: (
                    item.criterion.value,
                    item.code,
                    item.evidence_ids,
                ),
            )
        )

    @classmethod
    def _remediable_limitations(
        cls,
        trace: Sequence[CriterionTrace],
    ) -> tuple[MatchExplanation, ...]:
        return tuple(
            MatchExplanation(
                criterion=ExplanationCriterion(item.criterion.value),
                code="MANDATORY_REMEDIABLE_LIMITATION"
                if item.mandatory
                else "REMEDIABLE_LIMITATION",
                message="The criterion has a declared remediable limitation.",
                evidence_ids=item.evidence_ids,
            )
            for item in trace
            if item.remediable
        )

    @classmethod
    def _missing_reasons(
        cls,
        opportunity: PreparedOpportunityInput,
        match_result: MatchResult,
        trace: Sequence[CriterionTrace],
        *,
        capabilities: bool,
    ) -> tuple[MatchExplanation, ...]:
        profile_origins = {
            UnknownOrigin.ENTERPRISE_PROFILE,
            UnknownOrigin.MISSING_PROFILE_CAPABILITY,
        }
        reasons: list[MatchExplanation] = []
        for dimension in match_result.dimensions:
            criterion = _DIMENSION_CRITERIA.get(dimension.dimension)
            if criterion is None:
                continue
            for atom in dimension.atoms:
                if atom.state != AtomicMatchState.UNKNOWN:
                    continue
                is_capability = atom.origin in profile_origins
                if is_capability == capabilities:
                    reasons.append(cls._atom_explanation(criterion, atom))

        if capabilities:
            generated = {
                MatchingCriterion.QUANTITY_CAPACITY,
                MatchingCriterion.EXECUTION_DEADLINE,
            }
            if opportunity.region_code is not None:
                generated.add(MatchingCriterion.REGION_LOGISTICS)
        else:
            generated = (
                {MatchingCriterion.REGION_LOGISTICS}
                if opportunity.region_code is None
                else set()
            )
        trace_by_criterion = {item.criterion: item for item in trace}
        for criterion in generated:
            code, message = cls._generated_unknown_reason(opportunity, criterion)
            item = trace_by_criterion[criterion]
            reasons.append(
                MatchExplanation(
                    criterion=ExplanationCriterion(criterion.value),
                    code=code,
                    message=message,
                    evidence_ids=item.evidence_ids,
                )
            )
        return tuple(
            sorted(
                reasons,
                key=lambda item: (
                    item.criterion.value,
                    item.code,
                    item.evidence_ids,
                ),
            )
        )


def _deadline_sort_key(value: Deadline) -> tuple[int, int, int, int]:
    if value is None:
        return (1, 0, 0, 0)
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC)
        microseconds = (
            normalized.hour * 3_600_000_000
            + normalized.minute * 60_000_000
            + normalized.second * 1_000_000
            + normalized.microsecond
        )
        return (0, normalized.date().toordinal(), 1, microseconds)
    return (0, value.toordinal(), 0, 0)


def top_matches(results: Iterable[ScoredMatchResult]) -> tuple[ScoredMatchResult, ...]:
    """Exclude only terminal statuses, apply the binding order, and take ten."""
    excluded = {MatchStatus.NOT_ELIGIBLE, MatchStatus.INCOMPATIBLE}
    eligible = [item for item in results if item.match_status not in excluded]
    eligible.sort(
        key=lambda item: (
            -item.ranking_score,
            -item.coverage,
            _deadline_sort_key(item.application_deadline),
            item.opportunity_identity.source,
            item.opportunity_identity.external_id,
        )
    )
    return tuple(eligible[:10])
