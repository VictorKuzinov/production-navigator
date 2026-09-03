from datetime import date, datetime

from app.core.exceptions import EnterpriseProfileNotFoundError
from app.matching.engine import ProcurementMatchingEngine
from app.matching.scoring import ProcurementMatchingScoringEngine, top_matches
from app.repositories.procurement_matching import (
    ProfileMatchingProjectionRepository,
)
from app.repositories.procurement_opportunities import (
    ProcurementOpportunityRepository,
)
from app.schemas.procurement_matching import (
    MatchEvaluationContext,
    MatchResult,
    ProfileMatchingSnapshot,
)
from app.schemas.procurement_matching_scoring import (
    RankingEvaluationContext,
    ScoredMatchResult,
)
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.services.procurement_opportunities import (
    canonical_opportunity_from_aggregate,
)


class ProcurementOpportunityNotFoundError(Exception):
    """The requested procurement opportunity does not exist."""


class ProcurementMatchingService:
    """Read-only orchestration for one opportunity/profile pair."""

    def __init__(
        self,
        opportunity_repository: ProcurementOpportunityRepository,
        profile_repository: ProfileMatchingProjectionRepository,
        engine: ProcurementMatchingEngine | None = None,
        scoring_engine: ProcurementMatchingScoringEngine | None = None,
    ):
        self.opportunity_repository = opportunity_repository
        self.profile_repository = profile_repository
        self.engine = engine or ProcurementMatchingEngine()
        self.scoring_engine = scoring_engine or ProcurementMatchingScoringEngine()

    async def match(
        self,
        opportunity_id: int,
        profile_id: int,
        evaluation_date: date,
    ) -> MatchResult:
        opportunity = await self.opportunity_repository.get_by_id(opportunity_id)
        if opportunity is None:
            raise ProcurementOpportunityNotFoundError(
                f"Procurement opportunity {opportunity_id} was not found."
            )
        profile = await self.profile_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} was not found."
            )
        canonical_opportunity = canonical_opportunity_from_aggregate(opportunity)
        return self.engine.match(
            opportunity_id=opportunity.id,
            opportunity=canonical_opportunity,
            profile=profile,
            context=MatchEvaluationContext(evaluation_date=evaluation_date),
        )

    async def score_match(
        self,
        opportunity_id: int,
        profile_id: int,
        evaluation_time: datetime,
    ) -> ScoredMatchResult:
        context = RankingEvaluationContext(evaluation_time=evaluation_time)
        opportunity = await self.opportunity_repository.get_by_id(opportunity_id)
        if opportunity is None:
            raise ProcurementOpportunityNotFoundError(
                f"Procurement opportunity {opportunity_id} was not found."
            )
        profile = await self._get_profile(profile_id)
        canonical = canonical_opportunity_from_aggregate(opportunity)
        return self._score_canonical(opportunity.id, canonical, profile, context)

    async def top_matches(
        self,
        profile_id: int,
        evaluation_time: datetime,
    ) -> tuple[ScoredMatchResult, ...]:
        context = RankingEvaluationContext(evaluation_time=evaluation_time)
        profile = await self._get_profile(profile_id)
        opportunities = await self.opportunity_repository.list_all()
        scored = []
        for opportunity in opportunities:
            canonical = canonical_opportunity_from_aggregate(opportunity)
            scored.append(
                self._score_canonical(
                    opportunity.id,
                    canonical,
                    profile,
                    context,
                )
            )
        return top_matches(scored)

    async def _get_profile(self, profile_id: int) -> ProfileMatchingSnapshot:
        profile = await self.profile_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} was not found."
            )
        return profile

    def _score_canonical(
        self,
        opportunity_id: int,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
        context: RankingEvaluationContext,
    ) -> ScoredMatchResult:
        match_result = self.engine.match(
            opportunity_id=opportunity_id,
            opportunity=opportunity,
            profile=profile,
            context=MatchEvaluationContext(
                evaluation_date=context.evaluation_time.date()
            ),
        )
        return self.scoring_engine.score(opportunity, match_result, context)
