import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    MaterialInUseError,
    MaterialReclassificationBlockedError,
)
from app.models import CapabilityState, Material
from app.repositories import (
    EnterpriseProfileRepository,
    MaterialRepository,
    ProfileMaterialCapabilityRepository,
    ProfileSectionCompletenessRepository,
    ProfileTechnologyCapabilityRepository,
    ReferenceRepository,
)
from app.schemas import EnterpriseProfileCreate, MaterialUpdate
from app.services.materials import MaterialService
from app.services.profile_capabilities import ProfileCapabilityService


async def create_context(
    db_session: AsyncSession,
    group_code: str,
):
    profile = await EnterpriseProfileRepository(db_session).create(
        EnterpriseProfileCreate(
            company_name="Lifecycle profile",
            inn="6673000001",
        )
    )
    material = Material(group_code=group_code, grade_name="Сталь 45")
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    material_repository = MaterialRepository(db_session)
    references = ReferenceRepository(db_session)
    capability_service = ProfileCapabilityService(
        session=db_session,
        technology_repository=ProfileTechnologyCapabilityRepository(db_session),
        material_capability_repository=ProfileMaterialCapabilityRepository(db_session),
        section_repository=ProfileSectionCompletenessRepository(db_session),
        enterprise_repository=EnterpriseProfileRepository(db_session),
        reference_repository=references,
        material_repository=material_repository,
    )
    material_service = MaterialService(material_repository, references)
    return profile, material, capability_service, material_service


async def test_material_delete_is_blocked_by_specific_capability(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile, material, capability_service, material_service = await create_context(
        db_session,
        reference_rows["material_group"],
    )
    await capability_service.put_material_capability(
        profile.id,
        material.id,
        CapabilityState.SUPPORTED,
    )

    with pytest.raises(MaterialInUseError):
        await material_service.delete_material(material.id)


async def test_material_reclassification_is_blocked_by_specific_capability(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile, material, capability_service, material_service = await create_context(
        db_session,
        reference_rows["material_group"],
    )
    await capability_service.put_material_capability(
        profile.id,
        material.id,
        CapabilityState.UNKNOWN,
    )

    with pytest.raises(MaterialReclassificationBlockedError):
        await material_service.update_material(
            material.id,
            MaterialUpdate(group_code=reference_rows["other_material_group"]),
        )


@pytest.mark.parametrize("dependency_side", ["old", "new"])
async def test_material_reclassification_is_blocked_by_affected_group_capability(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    dependency_side: str,
) -> None:
    profile, material, capability_service, material_service = await create_context(
        db_session,
        reference_rows["material_group"],
    )
    dependency_group = (
        reference_rows["material_group"]
        if dependency_side == "old"
        else reference_rows["other_material_group"]
    )
    await capability_service.put_material_group_capability(
        profile.id,
        dependency_group,
        CapabilityState.SUPPORTED,
    )

    with pytest.raises(MaterialReclassificationBlockedError):
        await material_service.update_material(
            material.id,
            MaterialUpdate(group_code=reference_rows["other_material_group"]),
        )


async def test_material_reclassification_succeeds_without_capability_dependency(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    _, material, _, material_service = await create_context(
        db_session,
        reference_rows["material_group"],
    )

    updated = await material_service.update_material(
        material.id,
        MaterialUpdate(group_code=reference_rows["other_material_group"]),
    )

    assert updated.group_code == reference_rows["other_material_group"]
