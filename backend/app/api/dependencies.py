from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_session
from app.repositories import ReferenceRepository
from app.repositories.enterprises import EnterpriseProfileRepository
from app.services.enterprises import EnterpriseProfileService

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

def get_enterprise_service(
    session: SessionDep,
) -> EnterpriseProfileService:
    repository = EnterpriseProfileRepository(session)
    reference_repository = ReferenceRepository(session)

    return EnterpriseProfileService(
        repository,
        reference_repository,
    )