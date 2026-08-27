from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile, Product, ProductType
from app.repositories.material_items import MaterialItemRepository
from app.repositories.materials import MaterialRepository
from app.schemas import (
    MaterialCreate,
    MaterialItemCreate,
    MaterialItemUpdate,
)


async def create_material(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
):
    return await MaterialRepository(db_session).create(
        MaterialCreate(
            group_code=reference_rows["material_group"],
            grade_name="Сталь 20",
        )
    )


async def test_material_item_repository_crud_and_nullable_identity_lookup(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(db_session, reference_rows)
    repository = MaterialItemRepository(db_session)
    created = await repository.create(
        MaterialItemCreate(
            material_id=material.id,
            material_form_code=reference_rows["material_form"],
            dimension_1=20.0,
            unit_of_measure="kg",
        )
    )

    fetched = await repository.get_by_id(created.id)
    identity_match = await repository.get_by_identity(
        material.id,
        reference_rows["material_form"],
        20.0,
        "kg",
    )
    listed = await repository.list_material_items()

    assert fetched is created
    assert identity_match is created
    assert [item.id for item in listed] == [created.id]

    cleared = await repository.update(
        created.id,
        MaterialItemUpdate(dimension_1=None, unit_of_measure="m"),
    )
    assert cleared is not None
    assert cleared.dimension_1 is None
    assert cleared.unit_of_measure == "m"
    assert (
        await repository.get_by_identity(
            material.id,
            reference_rows["material_form"],
            None,
            "m",
        )
        is created
    )

    unchanged = await repository.update(created.id, MaterialItemUpdate())
    assert unchanged is not None
    assert unchanged.dimension_1 is None
    assert unchanged.unit_of_measure == "m"

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None


async def test_material_item_repository_reports_product_usage(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(db_session, reference_rows)
    repository = MaterialItemRepository(db_session)
    item = await repository.create(
        MaterialItemCreate(
            material_id=material.id,
            material_form_code=reference_rows["material_form"],
            dimension_1=None,
            unit_of_measure="kg",
        )
    )

    assert await repository.has_products(item.id) is False

    product_type = ProductType(
        code="TEST_PRODUCT_TYPE",
        name_ru="Тестовый тип продукции",
        ics_section="25.000.00",
        ref_system="Test",
        ref_code="TEST_PRODUCT_TYPE",
        description="Test fixture for MaterialItem lifecycle.",
    )
    product = Product(
        profile_id=enterprise_row.id,
        product_type_code=product_type.code,
        material_item_id=item.id,
        sku_code="TEST-SKU-1",
        name="Тестовое изделие",
        weight_net=1.0,
    )
    db_session.add_all([product_type, product])
    await db_session.commit()

    assert await repository.has_products(item.id) is True


async def test_material_item_repository_returns_none_for_missing_mutations(
    db_session: AsyncSession,
) -> None:
    repository = MaterialItemRepository(db_session)

    assert await repository.update(999, MaterialItemUpdate()) is None
    assert await repository.delete(999) is None
