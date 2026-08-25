from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaterialItem
from app.repositories.materials import MaterialRepository
from app.schemas import MaterialCreate, MaterialUpdate


async def test_material_repository_crud_and_duplicate_query(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = MaterialRepository(db_session)
    created = await repository.create(
        MaterialCreate(
            group_code=reference_rows["material_group"],
            grade_name="Сталь 45",
            density=7850.0,
        )
    )

    fetched = await repository.get_by_id(created.id)
    duplicate = await repository.get_by_group_and_grade(
        reference_rows["material_group"],
        "Сталь 45",
    )
    listed = await repository.list_materials()

    assert fetched is created
    assert duplicate is created
    assert [material.id for material in listed] == [created.id]

    changed = await repository.update(
        created.id,
        MaterialUpdate(
            group_code=reference_rows["other_material_group"],
            grade_name="40Х",
            density=7800.0,
        ),
    )
    assert changed is not None
    assert changed.group_code == reference_rows["other_material_group"]
    assert changed.grade_name == "40Х"
    assert changed.density == 7800.0

    cleared = await repository.update(
        created.id,
        MaterialUpdate(density=None),
    )
    assert cleared is not None
    assert cleared.density is None
    assert cleared.grade_name == "40Х"

    unchanged = await repository.update(created.id, MaterialUpdate())
    assert unchanged is not None
    assert unchanged.density is None
    assert unchanged.grade_name == "40Х"

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None


async def test_material_repository_reports_material_item_existence(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = MaterialRepository(db_session)
    material = await repository.create(
        MaterialCreate(
            group_code=reference_rows["material_group"],
            grade_name="Сталь 20",
        )
    )

    assert await repository.has_material_items(material.id) is False

    item = MaterialItem(
        material_id=material.id,
        material_form_code=reference_rows["material_form"],
        dimension_1=20.0,
        unit_of_measure="kg",
    )
    db_session.add(item)
    await db_session.commit()

    assert await repository.has_material_items(material.id) is True


async def test_material_repository_returns_none_for_missing_mutations(
    db_session: AsyncSession,
) -> None:
    repository = MaterialRepository(db_session)

    assert await repository.update(999, MaterialUpdate()) is None
    assert await repository.delete(999) is None
