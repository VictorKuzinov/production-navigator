from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EnterpriseProfile,
    Industry,
    OrderType,
    ProductionOrder,
    ProductType,
)
from app.repositories.material_items import MaterialItemRepository
from app.repositories.materials import MaterialRepository
from app.repositories.products import ProductRepository
from app.schemas import (
    MaterialCreate,
    MaterialItemCreate,
    ProductCreate,
    ProductUpdate,
)


async def create_product_dependencies(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> tuple[str, int]:
    product_type = ProductType(
        code="FINISHED_GOOD",
        name_ru="Готовое изделие",
        ics_section="25.000.00",
        ref_system="Test",
        ref_code="FINISHED_GOOD",
        description="Test fixture for Product repository.",
    )
    db_session.add(product_type)
    await db_session.commit()

    material = await MaterialRepository(db_session).create(
        MaterialCreate(
            group_code=reference_rows["material_group"],
            grade_name="Сталь Product repository",
        )
    )
    material_item = await MaterialItemRepository(db_session).create(
        MaterialItemCreate(
            material_id=material.id,
            material_form_code=reference_rows["material_form"],
            dimension_1=20.0,
            unit_of_measure="kg",
        )
    )
    return product_type.code, material_item.id


def product_data(
    product_type_code: str,
    material_item_id: int,
    sku_code: str = "Repo-SKU",
) -> ProductCreate:
    return ProductCreate(
        product_type_code=product_type_code,
        material_item_id=material_item_id,
        sku_code=sku_code,
        name="Repository product",
        weight_net=12.5,
        required_it_grade=8,
        required_ra=1.6,
    )


async def test_product_repository_crud_and_exact_profile_sku_lookup(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    product_type_code, material_item_id = await create_product_dependencies(
        db_session,
        reference_rows,
    )
    repository = ProductRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        product_data(product_type_code, material_item_id, "Case-SKU"),
    )
    case_variant = await repository.create(
        enterprise_row.id,
        product_data(product_type_code, material_item_id, "case-sku"),
    )

    fetched = await repository.get_by_id(created.id)
    exact = await repository.get_by_profile_sku(enterprise_row.id, "Case-SKU")
    wrong_case = await repository.get_by_profile_sku(
        enterprise_row.id,
        "CASE-SKU",
    )
    listed = await repository.list_by_profile(enterprise_row.id)

    assert fetched is created
    assert exact is created
    assert wrong_case is None
    assert [product.id for product in listed] == [created.id, case_variant.id]

    updated = await repository.update(
        created.id,
        ProductUpdate(
            sku_code="Updated-SKU",
            name="Updated product",
            required_it_grade=None,
            required_ra=None,
        ),
    )
    assert updated is created
    assert updated.sku_code == "Updated-SKU"
    assert updated.required_it_grade is None
    assert updated.required_ra is None

    unchanged = await repository.update(created.id, ProductUpdate())
    assert unchanged is created
    assert unchanged.name == "Updated product"

    deleted = await repository.delete(created.id)
    assert deleted is created
    assert await repository.get_by_id(created.id) is None


async def test_product_repository_reports_production_order_usage(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    product_type_code, material_item_id = await create_product_dependencies(
        db_session,
        reference_rows,
    )
    repository = ProductRepository(db_session)
    product = await repository.create(
        enterprise_row.id,
        product_data(product_type_code, material_item_id),
    )

    assert await repository.has_orders(product.id) is False

    order_type = OrderType(
        code="TEST_ORDER_TYPE",
        name_ru="Тестовый тип заказа",
        ics_section="03.100.50",
        ref_system="Test",
        ref_code="TEST_ORDER_TYPE",
        description="Test fixture for Product lifecycle.",
    )
    industry = Industry(
        code="TEST_INDUSTRY",
        name_ru="Тестовая отрасль",
        ics_section="25.000.00",
        ref_system="Test",
        ref_code="TEST_INDUSTRY",
        description="Test fixture for Product lifecycle.",
    )
    order = ProductionOrder(
        profile_id=enterprise_row.id,
        order_type_code=order_type.code,
        product_id=product.id,
        industry_code=industry.code,
        order_number="ORDER-1",
        quantity=1,
        deadline=date(2027, 1, 1),
    )
    db_session.add_all([order_type, industry, order])
    await db_session.commit()

    assert await repository.has_orders(product.id) is True


async def test_product_repository_returns_none_for_missing_mutations(
    db_session: AsyncSession,
) -> None:
    repository = ProductRepository(db_session)

    assert await repository.update(999, ProductUpdate()) is None
    assert await repository.delete(999) is None
