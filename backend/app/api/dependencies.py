from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_session
from app.repositories import (
    EquipmentRepository,
    LiftingEquipmentRepository,
    ProductionFacilityRepository,
    ReferenceRepository,
    WarehouseRepository,
)
from app.repositories.enterprises import EnterpriseProfileRepository
from app.services.enterprises import EnterpriseProfileService
from app.services.equipments import EquipmentService
from app.services.lifting_equipments import LiftingEquipmentService
from app.services.production_facilities import ProductionFacilityService
from app.services.warehouses import WarehouseService

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


def get_facility_service(
    session: SessionDep,
) -> ProductionFacilityService:
    repository = ProductionFacilityRepository(session)
    enterprise_repository = EnterpriseProfileRepository(session)
    
    return ProductionFacilityService(
        repository,
        enterprise_repository,
    )

def get_equipment_service(
    session: SessionDep,
) -> EquipmentService:
    repository = EquipmentRepository(session)
    enterprise_repository = EnterpriseProfileRepository(session)
    facility_repository = ProductionFacilityRepository(session)
    reference_repository = ReferenceRepository(session)

    return EquipmentService(
        repository,
        enterprise_repository,
        facility_repository,
        reference_repository,
    )


def get_warehouse_service(
    session: SessionDep,
) -> WarehouseService:
    repository = WarehouseRepository(session)
    enterprise_repository = EnterpriseProfileRepository(session)
    reference_repository = ReferenceRepository(session)

    return WarehouseService(
        repository,
        enterprise_repository,
        reference_repository,
    )


def get_lifting_equipment_service(
    session: SessionDep,
) -> LiftingEquipmentService:
    repository = LiftingEquipmentRepository(session)
    enterprise_repository = EnterpriseProfileRepository(session)
    facility_repository = ProductionFacilityRepository(session)
    warehouse_repository = WarehouseRepository(session)
    reference_repository = ReferenceRepository(session)

    return LiftingEquipmentService(
        repository,
        enterprise_repository,
        facility_repository,
        warehouse_repository,
        reference_repository,
    )
