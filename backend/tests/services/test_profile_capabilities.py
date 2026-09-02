from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CapabilitySectionIntegrityError,
    EnterpriseProfileNotFoundError,
    MaterialGroupNotFoundError,
    MaterialNotFoundError,
    TechnologyTypeNotFoundError,
)
from app.models import (
    CapabilityState,
    EnterpriseProfile,
    Material,
    ProfileSectionCode,
    ProfileSectionCompleteness,
    ProfileSectionState,
)
from app.repositories import (
    EnterpriseProfileRepository,
    MaterialRepository,
    ProfileMaterialCapabilityRepository,
    ProfileSectionCompletenessRepository,
    ProfileTechnologyCapabilityRepository,
    ReferenceRepository,
)
from app.schemas import EnterpriseProfileCreate
from app.services.profile_capabilities import NO_ASSERTION, ProfileCapabilityService


def build_service(db_session: AsyncSession) -> ProfileCapabilityService:
    return ProfileCapabilityService(
        session=db_session,
        technology_repository=ProfileTechnologyCapabilityRepository(db_session),
        material_capability_repository=ProfileMaterialCapabilityRepository(db_session),
        section_repository=ProfileSectionCompletenessRepository(db_session),
        enterprise_repository=EnterpriseProfileRepository(db_session),
        reference_repository=ReferenceRepository(db_session),
        material_repository=MaterialRepository(db_session),
    )


async def create_profile(db_session: AsyncSession, suffix: int) -> EnterpriseProfile:
    return await EnterpriseProfileRepository(db_session).create(
        EnterpriseProfileCreate(
            company_name=f"Service capability profile {suffix}",
            inn=f"667200{suffix:04d}",
        )
    )


async def create_material(
    db_session: AsyncSession,
    group_code: str,
    grade_name: str = "Сталь 45",
) -> Material:
    material = Material(group_code=group_code, grade_name=grade_name)
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest.mark.parametrize("state", list(CapabilityState))
async def test_technology_supports_each_explicit_state_and_resolution(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    state: CapabilityState,
) -> None:
    profile = await create_profile(db_session, 1)
    service = build_service(db_session)

    capability = await service.put_technology_capability(
        profile.id,
        reference_rows["technology_type"],
        state,
    )

    assert capability.state == state
    assert await service.list_technology_capabilities(profile.id) == [capability]
    assert (
        await service.resolve_technology_capability(
            profile.id,
            reference_rows["technology_type"],
        )
        == state
    )


async def test_absent_technology_is_no_assertion(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 2)
    service = build_service(db_session)

    assert (
        await service.resolve_technology_capability(
            profile.id,
            reference_rows["technology_type"],
        )
        == NO_ASSERTION
    )


async def test_technology_validates_profile_and_reference(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 3)
    service = build_service(db_session)

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.put_technology_capability(
            999_999,
            reference_rows["technology_type"],
            CapabilityState.SUPPORTED,
        )
    with pytest.raises(TechnologyTypeNotFoundError):
        await service.put_technology_capability(
            profile.id,
            "NO_SUCH_TECHNOLOGY",
            CapabilityState.SUPPORTED,
        )


async def test_semantic_technology_mutations_invalidate_but_noops_do_not(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 4)
    service = build_service(db_session)
    technology_code = reference_rows["technology_type"]

    await service.confirm_section(
        profile.id,
        ProfileSectionCode.TECHNOLOGIES,
        "operator-create",
    )
    await service.put_technology_capability(
        profile.id,
        technology_code,
        CapabilityState.SUPPORTED,
    )
    section = await service.list_sections(profile.id)
    technologies = section[0]
    assert technologies.state == ProfileSectionState.PARTIAL
    assert technologies.confirmed_by is None
    assert technologies.confirmed_at is None

    confirmed = await service.confirm_section(
        profile.id,
        ProfileSectionCode.TECHNOLOGIES,
        "operator-noop",
    )
    timestamp = confirmed.confirmed_at
    same = await service.put_technology_capability(
        profile.id,
        technology_code,
        CapabilityState.SUPPORTED,
    )
    await service.delete_technology_capability(
        profile.id,
        reference_rows["other_technology_type"],
    )
    assert same.state == CapabilityState.SUPPORTED
    unchanged = (await service.list_sections(profile.id))[0]
    assert unchanged.state == ProfileSectionState.CONFIRMED_COMPLETE
    assert unchanged.confirmed_at == timestamp
    assert unchanged.confirmed_by == "operator-noop"

    await service.put_technology_capability(
        profile.id,
        technology_code,
        CapabilityState.UNSUPPORTED,
    )
    assert (await service.list_sections(profile.id))[0].state == (
        ProfileSectionState.PARTIAL
    )

    await service.confirm_section(
        profile.id,
        ProfileSectionCode.TECHNOLOGIES,
        "operator-delete",
    )
    await service.delete_technology_capability(profile.id, technology_code)
    deleted_section = (await service.list_sections(profile.id))[0]
    assert deleted_section.state == ProfileSectionState.PARTIAL
    assert deleted_section.confirmed_by is None
    assert await service.list_technology_capabilities(profile.id) == []


async def test_technology_capabilities_are_isolated_by_profile(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    first = await create_profile(db_session, 5)
    second = await create_profile(db_session, 6)
    service = build_service(db_session)
    code = reference_rows["technology_type"]

    await service.put_technology_capability(
        first.id,
        code,
        CapabilityState.SUPPORTED,
    )
    await service.delete_technology_capability(second.id, code)

    assert len(await service.list_technology_capabilities(first.id)) == 1
    assert await service.list_technology_capabilities(second.id) == []


@pytest.mark.parametrize(
    ("group_state", "specific_state", "expected"),
    [
        (None, None, NO_ASSERTION),
        (CapabilityState.SUPPORTED, None, CapabilityState.SUPPORTED),
        (
            CapabilityState.SUPPORTED,
            CapabilityState.UNSUPPORTED,
            CapabilityState.UNSUPPORTED,
        ),
        (
            CapabilityState.UNSUPPORTED,
            CapabilityState.SUPPORTED,
            CapabilityState.SUPPORTED,
        ),
        (
            CapabilityState.UNKNOWN,
            CapabilityState.SUPPORTED,
            CapabilityState.SUPPORTED,
        ),
        (
            CapabilityState.SUPPORTED,
            CapabilityState.UNKNOWN,
            CapabilityState.UNKNOWN,
        ),
    ],
)
async def test_material_resolution_uses_specific_then_group_then_no_assertion(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    group_state: CapabilityState | None,
    specific_state: CapabilityState | None,
    expected: CapabilityState | str,
) -> None:
    profile = await create_profile(db_session, 7)
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    service = build_service(db_session)

    if group_state is not None:
        await service.put_material_group_capability(
            profile.id,
            reference_rows["material_group"],
            group_state,
        )
    if specific_state is not None:
        await service.put_material_capability(
            profile.id,
            material.id,
            specific_state,
        )

    assert await service.resolve_material_capability(profile.id, material.id) == (
        expected
    )


async def test_group_resolution_never_aggregates_specific_rows(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 8)
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    service = build_service(db_session)
    await service.put_material_capability(
        profile.id,
        material.id,
        CapabilityState.SUPPORTED,
    )

    assert (
        await service.resolve_material_group_capability(
            profile.id,
            reference_rows["material_group"],
        )
        == NO_ASSERTION
    )


async def test_material_capabilities_validate_targets_and_isolate_profiles(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    first = await create_profile(db_session, 9)
    second = await create_profile(db_session, 10)
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    service = build_service(db_session)

    with pytest.raises(MaterialGroupNotFoundError):
        await service.put_material_group_capability(
            first.id,
            "NO_SUCH_GROUP",
            CapabilityState.SUPPORTED,
        )
    with pytest.raises(MaterialNotFoundError):
        await service.put_material_capability(
            first.id,
            999_999,
            CapabilityState.SUPPORTED,
        )

    await service.put_material_capability(
        first.id,
        material.id,
        CapabilityState.UNKNOWN,
    )
    await service.delete_material_capability(second.id, material.id)
    assert len(await service.list_material_capabilities(first.id)) == 1
    assert await service.list_material_capabilities(second.id) == []


async def test_empty_section_state_and_reconfirmation_contract(
    db_session: AsyncSession,
) -> None:
    profile = await create_profile(db_session, 11)
    service = build_service(db_session)

    sections = await service.list_sections(profile.id)
    assert [section.state for section in sections] == [
        ProfileSectionState.UNKNOWN,
        ProfileSectionState.UNKNOWN,
    ]

    partial = await service.set_section_state(
        profile.id,
        ProfileSectionCode.MATERIALS,
        ProfileSectionState.PARTIAL,
    )
    assert partial.state == ProfileSectionState.PARTIAL
    repeated = await service.set_section_state(
        profile.id,
        ProfileSectionCode.MATERIALS,
        ProfileSectionState.PARTIAL,
    )
    assert repeated is partial

    first = await service.confirm_section(
        profile.id,
        ProfileSectionCode.MATERIALS,
        "operator-one",
    )
    first_timestamp = first.confirmed_at
    second = await service.confirm_section(
        profile.id,
        ProfileSectionCode.MATERIALS,
        "operator-two",
    )
    assert second.state == ProfileSectionState.CONFIRMED_COMPLETE
    assert second.confirmed_by == "operator-two"
    assert second.confirmed_at is not None
    assert first_timestamp is not None
    assert second.confirmed_at > first_timestamp

    with pytest.raises(ValueError):
        await service.set_section_state(
            profile.id,
            ProfileSectionCode.MATERIALS,
            ProfileSectionState.CONFIRMED_COMPLETE,
        )

    with pytest.raises(ValueError):
        await service.confirm_section(
            profile.id,
            ProfileSectionCode.MATERIALS,
            "   ",
        )


async def test_mutation_preserves_unknown_and_partial_section_states(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 14)
    service = build_service(db_session)

    await service.put_technology_capability(
        profile.id,
        reference_rows["technology_type"],
        CapabilityState.SUPPORTED,
    )
    assert (await service.list_sections(profile.id))[0].state == (
        ProfileSectionState.UNKNOWN
    )

    await service.set_section_state(
        profile.id,
        ProfileSectionCode.MATERIALS,
        ProfileSectionState.PARTIAL,
    )
    await service.put_material_group_capability(
        profile.id,
        reference_rows["material_group"],
        CapabilityState.UNKNOWN,
    )
    assert (await service.list_sections(profile.id))[1].state == (
        ProfileSectionState.PARTIAL
    )


async def test_material_semantic_mutations_and_noops_follow_invalidation_contract(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, 15)
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    service = build_service(db_session)

    await service.confirm_section(
        profile.id,
        ProfileSectionCode.MATERIALS,
        "operator-create",
    )
    await service.put_material_group_capability(
        profile.id,
        reference_rows["material_group"],
        CapabilityState.SUPPORTED,
    )
    assert (await service.list_sections(profile.id))[1].state == (
        ProfileSectionState.PARTIAL
    )

    confirmed = await service.confirm_section(
        profile.id,
        ProfileSectionCode.MATERIALS,
        "operator-noop",
    )
    timestamp = confirmed.confirmed_at
    await service.put_material_group_capability(
        profile.id,
        reference_rows["material_group"],
        CapabilityState.SUPPORTED,
    )
    await service.delete_material_capability(profile.id, material.id)
    unchanged = (await service.list_sections(profile.id))[1]
    assert unchanged.state == ProfileSectionState.CONFIRMED_COMPLETE
    assert unchanged.confirmed_at == timestamp

    await service.put_material_capability(
        profile.id,
        material.id,
        CapabilityState.UNKNOWN,
    )
    assert (await service.list_sections(profile.id))[1].state == (
        ProfileSectionState.PARTIAL
    )
    await service.confirm_section(
        profile.id,
        ProfileSectionCode.MATERIALS,
        "operator-delete",
    )
    await service.delete_material_capability(profile.id, material.id)
    deleted_section = (await service.list_sections(profile.id))[1]
    assert deleted_section.state == ProfileSectionState.PARTIAL
    assert deleted_section.confirmed_by is None


async def test_commit_failure_rolls_back_capability_and_invalidation(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = await create_profile(db_session, 12)
    profile_id = profile.id
    service = build_service(db_session)
    confirmed = await service.confirm_section(
        profile_id,
        ProfileSectionCode.TECHNOLOGIES,
        "operator",
    )
    original_timestamp = confirmed.confirmed_at
    real_commit = db_session.commit
    monkeypatch.setattr(
        db_session,
        "commit",
        AsyncMock(side_effect=RuntimeError("forced commit failure")),
    )

    with pytest.raises(RuntimeError, match="forced commit failure"):
        await service.put_technology_capability(
            profile_id,
            reference_rows["technology_type"],
            CapabilityState.SUPPORTED,
        )

    monkeypatch.setattr(db_session, "commit", real_commit)
    assert await service.list_technology_capabilities(profile_id) == []
    restored = (await service.list_sections(profile_id))[0]
    assert restored.state == ProfileSectionState.CONFIRMED_COMPLETE
    assert restored.confirmed_by == "operator"
    restored_timestamp = restored.confirmed_at
    if restored_timestamp is not None and restored_timestamp.tzinfo is None:
        restored_timestamp = restored_timestamp.replace(tzinfo=UTC)
    assert restored_timestamp == original_timestamp


async def test_missing_completeness_row_is_integrity_error_not_implicit_complete(
    db_session: AsyncSession,
) -> None:
    profile = await create_profile(db_session, 13)
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id,
            ProfileSectionCompleteness.section_code
            == ProfileSectionCode.TECHNOLOGIES,
        )
    )
    await db_session.commit()

    with pytest.raises(CapabilitySectionIntegrityError):
        await build_service(db_session).list_sections(profile.id)
