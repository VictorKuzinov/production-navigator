from datetime import date

from app.core.exceptions import EnterpriseProfileNotFoundError
from app.matching.engine import ProcurementMatchingEngine
from app.repositories.procurement_matching import (
    ProfileMatchingProjectionRepository,
)
from app.repositories.procurement_opportunities import (
    ProcurementOpportunityRepository,
)
from app.schemas.procurement_matching import MatchEvaluationContext, MatchResult
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
    ):
        self.opportunity_repository = opportunity_repository
        self.profile_repository = profile_repository
        self.engine = engine or ProcurementMatchingEngine()

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
