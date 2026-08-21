from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.enterprises import EnterpriseProfileRepository
from app.schemas import EnterpriseProfileCreate, EnterpriseProfileUpdate


async def test_enterprise_repository_crud_persists_patch_semantics(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = EnterpriseProfileRepository(db_session)
    created = await repository.create(
        EnterpriseProfileCreate(
            company_name="Repository enterprise",
            inn="6671000010",
            ogrn="1069600000010",
            website="https://before.example.test",
            employees_count=12,
            company_size_code=reference_rows["company_size"],
            region_code=reference_rows["region"],
        )
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_profiles()
    updated = await repository.update(
        created.id,
        EnterpriseProfileUpdate(website=None, employees_count=15),
    )

    assert fetched is not None
    assert [profile.id for profile in listed] == [created.id]
    assert updated is not None
    assert updated.website is None
    assert updated.employees_count == 15
    assert updated.company_name == "Repository enterprise"

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None
