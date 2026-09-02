from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CapabilityState,
    EnterpriseProfile,
    Material,
    MaterialGroup,
    ProfileMaterialCapability,
    ProfileSectionCode,
    ProfileSectionCompleteness,
    ProfileSectionState,
    ProfileTechnologyCapability,
    TechnologyType,
)
from app.models.profile_capabilities import CONFIRMER_WHITESPACE_CODEPOINTS
from app.repositories import (
    EnterpriseProfileRepository,
    ProfileMaterialCapabilityRepository,
    ProfileSectionCompletenessRepository,
    ProfileTechnologyCapabilityRepository,
)
from app.schemas import EnterpriseProfileCreate
from app.schemas.profile_capabilities import ProfileSectionConfirmation


async def create_profile(db_session: AsyncSession, suffix: str) -> EnterpriseProfile:
    return await EnterpriseProfileRepository(db_session).create(
        EnterpriseProfileCreate(
            company_name=f"Capability profile {suffix}",
            inn=f"6671001{int(suffix):03d}",
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


async def test_new_profile_gets_two_initial_unknown_sections_atomically(
    db_session: AsyncSession,
) -> None:
    profile = await create_profile(db_session, "001")
    sections = await ProfileSectionCompletenessRepository(
        db_session
    ).list_for_profile(profile.id)

    assert [section.section_code for section in sections] == [
        ProfileSectionCode.TECHNOLOGIES,
        ProfileSectionCode.MATERIALS,
    ]
    assert {section.state for section in sections} == {ProfileSectionState.UNKNOWN}
    assert all(section.confirmed_at is None for section in sections)
    assert all(section.confirmed_by is None for section in sections)


async def test_profile_creation_failure_rolls_back_profile_and_both_sections(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EnterpriseProfileRepository(db_session)
    real_commit = db_session.commit

    async def fail_after_flush() -> None:
        await db_session.flush()
        raise RuntimeError("forced profile transaction failure")

    monkeypatch.setattr(db_session, "commit", fail_after_flush)
    with pytest.raises(RuntimeError, match="forced profile transaction failure"):
        await repository.create(
            EnterpriseProfileCreate(
                company_name="Rolled back profile",
                inn="6671999999",
            )
        )
    monkeypatch.setattr(db_session, "commit", real_commit)

    result = await db_session.execute(
        select(EnterpriseProfile).where(EnterpriseProfile.inn == "6671999999")
    )
    assert result.scalar_one_or_none() is None
    sections = await db_session.execute(select(ProfileSectionCompleteness))
    assert sections.scalars().all() == []


async def test_technology_repository_flushes_without_committing(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "002")
    profile_id = profile.id
    repository = ProfileTechnologyCapabilityRepository(db_session)

    created = await repository.create(
        profile_id,
        reference_rows["technology_type"],
        CapabilityState.SUPPORTED,
    )

    assert created.id is not None
    assert db_session.in_transaction()

    await db_session.rollback()
    assert (
        await repository.get(profile_id, reference_rows["technology_type"])
        is None
    )


async def test_material_repository_supports_group_and_specific_crud_without_commit(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "003")
    profile_id = profile.id
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    repository = ProfileMaterialCapabilityRepository(db_session)

    group = await repository.create_group(
        profile_id,
        reference_rows["material_group"],
        CapabilityState.UNKNOWN,
    )
    specific = await repository.create_material(
        profile_id,
        material.id,
        CapabilityState.UNSUPPORTED,
    )
    listed = await repository.list_for_profile(profile_id)

    assert listed == [group, specific]
    await repository.update_state(group, CapabilityState.SUPPORTED)
    await repository.delete(specific)
    assert group.state == CapabilityState.SUPPORTED
    assert await repository.get_material(profile_id, material.id) is None
    assert db_session.in_transaction()

    await db_session.rollback()
    assert await repository.list_for_profile(profile_id) == []


@pytest.mark.parametrize("state", [None, "INVALID"])
async def test_db_rejects_missing_or_invalid_capability_state(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    state: str | None,
) -> None:
    profile = await create_profile(db_session, "004")
    row = ProfileTechnologyCapability(
        profile_id=profile.id,
        technology_code=reference_rows["technology_type"],
        state=state,
    )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_db_rejects_technology_duplicates_and_invalid_references(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "005")
    profile_id = profile.id
    db_session.add_all(
        [
            ProfileTechnologyCapability(
                profile_id=profile_id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.SUPPORTED,
            ),
            ProfileTechnologyCapability(
                profile_id=profile_id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.UNKNOWN,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    db_session.add(
        ProfileTechnologyCapability(
            profile_id=profile_id,
            technology_code="NO_SUCH_TECHNOLOGY",
            state=CapabilityState.SUPPORTED,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    db_session.add(
        ProfileTechnologyCapability(
            profile_id=999_999,
            technology_code=reference_rows["technology_type"],
            state=CapabilityState.SUPPORTED,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    ("group_code", "material_id"),
    [(None, None), ("STEEL_CARBON", 1)],
)
async def test_db_enforces_exactly_one_material_target(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    group_code: str | None,
    material_id: int | None,
) -> None:
    profile = await create_profile(db_session, "006")
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    actual_material_id = material.id if material_id is not None else None
    db_session.add(
        ProfileMaterialCapability(
            profile_id=profile.id,
            material_group_code=group_code,
            material_id=actual_material_id,
            state=CapabilityState.SUPPORTED,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize("target", ["group", "material"])
async def test_db_rejects_duplicate_material_target_identity(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    target: str,
) -> None:
    profile = await create_profile(db_session, "007")
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    common = {
        "profile_id": profile.id,
        "material_group_code": (
            reference_rows["material_group"] if target == "group" else None
        ),
        "material_id": material.id if target == "material" else None,
    }
    db_session.add_all(
        [
            ProfileMaterialCapability(**common, state=CapabilityState.SUPPORTED),
            ProfileMaterialCapability(**common, state=CapabilityState.UNKNOWN),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize("invalid_target", ["group", "material", "profile"])
async def test_db_rejects_invalid_material_capability_references(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    invalid_target: str,
) -> None:
    profile = await create_profile(db_session, "011")
    profile_id = profile.id
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    row = ProfileMaterialCapability(
        profile_id=999_999 if invalid_target == "profile" else profile_id,
        material_group_code=(
            "NO_SUCH_GROUP" if invalid_target == "group" else None
        ),
        material_id=(999_999 if invalid_target == "material" else None),
        state=CapabilityState.SUPPORTED,
    )
    if invalid_target == "profile":
        row.material_id = material.id
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "row",
    [
        ProfileSectionCompleteness(
            profile_id=1,
            section_code="OTHER",
            state=ProfileSectionState.UNKNOWN,
        ),
        ProfileSectionCompleteness(
            profile_id=1,
            section_code=ProfileSectionCode.TECHNOLOGIES,
            state="INVALID",
        ),
        ProfileSectionCompleteness(
            profile_id=1,
            section_code=ProfileSectionCode.TECHNOLOGIES,
            state=ProfileSectionState.CONFIRMED_COMPLETE,
        ),
        ProfileSectionCompleteness(
            profile_id=1,
            section_code=ProfileSectionCode.TECHNOLOGIES,
            state=ProfileSectionState.PARTIAL,
            confirmed_by="operator",
        ),
    ],
)
async def test_db_enforces_completeness_checks(
    db_session: AsyncSession,
    row: ProfileSectionCompleteness,
) -> None:
    profile = await create_profile(db_session, "008")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id
        )
    )
    row.profile_id = profile.id
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "confirmed_by",
    [
        "",
        " ",
        "   ",
        "\t",
        "\t\t",
        "\n",
        "\r",
        "\r\n",
        " \t ",
        "\t \n",
        " \r\n\t ",
        "\u00A0",
        "\u2003",
        "\u202F",
        "\u0085",
        "\u1680",
        "\u2001",
        "\u2028",
        "\u2029",
        "\u205F",
        "\u3000",
        " \u00A0 ",
        "\u00A0\u2003",
        "\u00A0\u2003\u202F",
        "\t\u00A0\u2003\r",
        "\u1680\u3000\u2001",
    ],
)
async def test_db_rejects_whitespace_only_confirmer_when_confirmed_complete(
    db_session: AsyncSession,
    confirmed_by: str,
) -> None:
    profile = await create_profile(db_session, "012")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id
        )
    )
    row = ProfileSectionCompleteness(
        profile_id=profile.id,
        section_code=ProfileSectionCode.TECHNOLOGIES,
        state=ProfileSectionState.CONFIRMED_COMPLETE,
        confirmed_at=datetime.now(UTC),
        confirmed_by=confirmed_by,
    )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "codepoint",
    CONFIRMER_WHITESPACE_CODEPOINTS,
)
async def test_db_rejects_each_fullset_whitespace_codepoint_as_only_confirmer(
    db_session: AsyncSession,
    codepoint: int,
) -> None:
    profile = await create_profile(db_session, "014")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id
        )
    )
    row = ProfileSectionCompleteness(
        profile_id=profile.id,
        section_code=ProfileSectionCode.TECHNOLOGIES,
        state=ProfileSectionState.CONFIRMED_COMPLETE,
        confirmed_at=datetime.now(UTC),
        confirmed_by=chr(codepoint),
    )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "codepoint",
    CONFIRMER_WHITESPACE_CODEPOINTS,
)
async def test_application_and_db_agree_fullset_whitespace_is_blank_confirmer(
    db_session: AsyncSession,
    codepoint: int,
) -> None:
    single_char = chr(codepoint)

    assert single_char.strip() == ""
    with pytest.raises(ValidationError):
        ProfileSectionConfirmation.model_validate({"confirmed_by": single_char})

    profile = await create_profile(db_session, "015")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id
        )
    )
    db_session.add(
        ProfileSectionCompleteness(
            profile_id=profile.id,
            section_code=ProfileSectionCode.TECHNOLOGIES,
            state=ProfileSectionState.CONFIRMED_COMPLETE,
            confirmed_at=datetime.now(UTC),
            confirmed_by=single_char,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "confirmed_by",
    [
        "operator-1",
        "Виктор",
        "  operator-2  ",
        "\tОлег\t",
        "\u00A0Boss\u00A0",
        "исполнитель\u3000",
    ],
)
async def test_db_accepts_nonwhitespace_confirmer_when_confirmed_complete(
    db_session: AsyncSession,
    confirmed_by: str,
) -> None:
    profile = await create_profile(db_session, "013")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id
        )
    )
    row = ProfileSectionCompleteness(
        profile_id=profile.id,
        section_code=ProfileSectionCode.TECHNOLOGIES,
        state=ProfileSectionState.CONFIRMED_COMPLETE,
        confirmed_at=datetime.now(UTC),
        confirmed_by=confirmed_by,
    )
    db_session.add(row)

    await db_session.flush()
    await db_session.rollback()


async def test_profile_delete_cascades_all_foundation_rows(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "009")
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    material_id = material.id
    db_session.add_all(
        [
            ProfileTechnologyCapability(
                profile_id=profile.id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.SUPPORTED,
            ),
            ProfileMaterialCapability(
                profile_id=profile.id,
                material_id=material_id,
                state=CapabilityState.SUPPORTED,
            ),
            ProfileMaterialCapability(
                profile_id=profile.id,
                material_group_code=reference_rows["other_material_group"],
                state=CapabilityState.UNKNOWN,
            ),
        ]
    )
    await db_session.commit()

    await db_session.execute(
        delete(EnterpriseProfile).where(EnterpriseProfile.id == profile.id)
    )
    await db_session.commit()

    for model in [
        ProfileTechnologyCapability,
        ProfileMaterialCapability,
        ProfileSectionCompleteness,
    ]:
        result = await db_session.execute(
            select(model).where(model.profile_id == profile.id)
        )
        assert result.scalars().all() == []


async def test_shared_references_use_restrictive_foreign_keys(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "010")
    material = await create_material(
        db_session,
        reference_rows["material_group"],
    )
    material_id = material.id
    db_session.add_all(
        [
            ProfileTechnologyCapability(
                profile_id=profile.id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.SUPPORTED,
            ),
            ProfileMaterialCapability(
                profile_id=profile.id,
                material_id=material_id,
                state=CapabilityState.SUPPORTED,
            ),
            ProfileMaterialCapability(
                profile_id=profile.id,
                material_group_code=reference_rows["other_material_group"],
                state=CapabilityState.UNKNOWN,
            ),
        ]
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            delete(TechnologyType).where(
                TechnologyType.code == reference_rows["technology_type"]
            )
        )
    await db_session.rollback()

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(Material).where(Material.id == material_id))
    await db_session.rollback()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            delete(MaterialGroup).where(
                MaterialGroup.code == reference_rows["material_group"]
            )
        )
    await db_session.rollback()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            delete(MaterialGroup).where(
                MaterialGroup.code == reference_rows["other_material_group"]
            )
        )
    await db_session.rollback()
