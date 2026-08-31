from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.exceptions import (
    DuplicateProductError,
    EnterpriseProfileNotFoundError,
    MaterialItemNotFoundError,
    ProductInUseError,
    ProductNotFoundError,
    ProductTypeNotFoundError,
)
from app.schemas import ProductCreate, ProductUpdate
from app.services.products import ProductService


def build_service(
    repository,
    enterprises,
    material_items,
    references,
) -> ProductService:
    return ProductService(
        repository,
        enterprises,
        material_items,
        references,
    )


def create_data() -> ProductCreate:
    return ProductCreate(
        product_type_code="FINISHED_GOOD",
        material_item_id=10,
        sku_code="Case-SKU",
        name="Product service fixture",
        weight_net=12.5,
        required_it_grade=8,
        required_ra=1.6,
    )


def product(**overrides: object) -> SimpleNamespace:
    values = {
        "id": 7,
        "profile_id": 3,
        "product_type_code": "FINISHED_GOOD",
        "material_item_id": 10,
        "sku_code": "Case-SKU",
        "name": "Product service fixture",
        "weight_net": 12.5,
        "required_it_grade": 8,
        "required_ra": 1.6,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def test_create_validates_references_and_duplicate_before_persisting() -> None:
    data = create_data()
    created = product()
    repository = SimpleNamespace(
        get_by_profile_sku=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created),
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    material_items = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(
        get_product_type_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, enterprises, material_items, references)
    calls = Mock()
    calls.attach_mock(enterprises.get_by_id, "profile")
    calls.attach_mock(references.get_product_type_by_code, "product_type")
    calls.attach_mock(material_items.get_by_id, "material_item")
    calls.attach_mock(repository.get_by_profile_sku, "duplicate")
    calls.attach_mock(repository.create, "create")

    result = await service.create_product(3, data)

    assert result is created
    assert calls.mock_calls == [
        call.profile(3),
        call.product_type("FINISHED_GOOD"),
        call.material_item(10),
        call.duplicate(3, "Case-SKU"),
        call.create(3, data),
    ]


async def test_create_rejects_missing_profile_before_other_checks() -> None:
    repository = SimpleNamespace(
        get_by_profile_sku=AsyncMock(),
        create=AsyncMock(),
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    material_items = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_product_type_by_code=AsyncMock())
    service = build_service(repository, enterprises, material_items, references)

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create_product(999, create_data())

    references.get_product_type_by_code.assert_not_awaited()
    material_items.get_by_id.assert_not_awaited()
    repository.get_by_profile_sku.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_unknown_product_type_before_material_item() -> None:
    repository = SimpleNamespace(
        get_by_profile_sku=AsyncMock(),
        create=AsyncMock(),
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    material_items = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(
        get_product_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, enterprises, material_items, references)

    with pytest.raises(ProductTypeNotFoundError):
        await service.create_product(3, create_data())

    material_items.get_by_id.assert_not_awaited()
    repository.get_by_profile_sku.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_unknown_material_item_before_duplicate() -> None:
    repository = SimpleNamespace(
        get_by_profile_sku=AsyncMock(),
        create=AsyncMock(),
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    material_items = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    references = SimpleNamespace(
        get_product_type_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, enterprises, material_items, references)

    with pytest.raises(MaterialItemNotFoundError):
        await service.create_product(3, create_data())

    repository.get_by_profile_sku.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_exact_duplicate_sku() -> None:
    repository = SimpleNamespace(
        get_by_profile_sku=AsyncMock(return_value=product()),
        create=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=object())),
        SimpleNamespace(get_by_id=AsyncMock(return_value=object())),
        SimpleNamespace(get_product_type_by_code=AsyncMock(return_value=object())),
    )

    with pytest.raises(DuplicateProductError):
        await service.create_product(3, create_data())

    repository.get_by_profile_sku.assert_awaited_once_with(3, "Case-SKU")
    repository.create.assert_not_awaited()


async def test_get_and_list_delegate_with_profile_validation() -> None:
    item = product()
    products = [item, product(id=8)]
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        list_by_profile=AsyncMock(return_value=products),
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    service = build_service(
        repository,
        enterprises,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    assert await service.get_product(7) is item
    assert await service.list_products(3) is products
    repository.get_by_id.assert_awaited_once_with(7)
    enterprises.get_by_id.assert_awaited_once_with(3)
    repository.list_by_profile.assert_awaited_once_with(3)


async def test_get_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductNotFoundError):
        await service.get_product(999)


async def test_list_rejects_missing_profile() -> None:
    repository = SimpleNamespace(list_by_profile=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(
        repository,
        enterprises,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.list_products(999)

    repository.list_by_profile.assert_not_awaited()


async def test_update_all_business_fields_validates_resulting_identity() -> None:
    item = product()
    update = ProductUpdate(
        product_type_code="SEMI_FINISHED",
        material_item_id=11,
        sku_code="New-SKU",
        name="New product",
        weight_net=20.0,
        required_it_grade=10,
        required_ra=0.8,
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(return_value=None),
        update=AsyncMock(return_value=item),
    )
    material_items = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(
        get_product_type_by_code=AsyncMock(return_value=object())
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        material_items,
        references,
    )

    assert await service.update_product(7, update) is item
    repository.has_orders.assert_awaited_once_with(7)
    references.get_product_type_by_code.assert_awaited_once_with(
        "SEMI_FINISHED"
    )
    material_items.get_by_id.assert_awaited_once_with(11)
    repository.get_by_profile_sku.assert_awaited_once_with(3, "New-SKU")
    repository.update.assert_awaited_once_with(7, update)


async def test_update_non_identity_field_skips_reference_and_duplicate_checks() -> None:
    item = product()
    update = ProductUpdate(name="Renamed")
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(),
        update=AsyncMock(return_value=item),
    )
    material_items = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_product_type_by_code=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(),
        material_items,
        references,
    )

    assert await service.update_product(7, update) is item
    references.get_product_type_by_code.assert_not_awaited()
    material_items.get_by_id.assert_not_awaited()
    repository.get_by_profile_sku.assert_not_awaited()
    repository.update.assert_awaited_once_with(7, update)


async def test_update_used_product_rejects_any_provided_field_first() -> None:
    item = product()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=True),
        get_by_profile_sku=AsyncMock(),
        update=AsyncMock(),
    )
    material_items = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_product_type_by_code=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(),
        material_items,
        references,
    )

    with pytest.raises(ProductInUseError):
        await service.update_product(7, ProductUpdate(name=item.name))

    references.get_product_type_by_code.assert_not_awaited()
    material_items.get_by_id.assert_not_awaited()
    repository.get_by_profile_sku.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_used_product_allows_empty_no_op() -> None:
    item = product()
    update = ProductUpdate()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(),
        get_by_profile_sku=AsyncMock(),
        update=AsyncMock(return_value=item),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    assert await service.update_product(7, update) is item
    repository.has_orders.assert_not_awaited()
    repository.get_by_profile_sku.assert_not_awaited()
    repository.update.assert_awaited_once_with(7, update)


async def test_update_allows_explicit_null_quality_without_duplicate_lookup() -> None:
    item = product()
    update = ProductUpdate(required_it_grade=None, required_ra=None)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(),
        update=AsyncMock(return_value=item),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    assert await service.update_product(7, update) is item
    repository.get_by_profile_sku.assert_not_awaited()
    repository.update.assert_awaited_once_with(7, update)


@pytest.mark.parametrize(
    ("update", "exception_type"),
    [
        (
            ProductUpdate(product_type_code="NO_SUCH_TYPE"),
            ProductTypeNotFoundError,
        ),
        (
            ProductUpdate(material_item_id=999),
            MaterialItemNotFoundError,
        ),
    ],
)
async def test_update_rejects_unknown_replacement_reference(
    update: ProductUpdate,
    exception_type: type[Exception],
) -> None:
    item = product()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(),
        update=AsyncMock(),
    )
    material_items = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    references = SimpleNamespace(
        get_product_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        material_items,
        references,
    )

    with pytest.raises(exception_type):
        await service.update_product(7, update)

    repository.get_by_profile_sku.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_rejects_duplicate_resulting_sku() -> None:
    item = product()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(return_value=product(id=8)),
        update=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(DuplicateProductError):
        await service.update_product(7, ProductUpdate(sku_code="Other-SKU"))

    repository.get_by_profile_sku.assert_awaited_once_with(3, "Other-SKU")
    repository.update.assert_not_awaited()


async def test_update_accepts_existing_self_for_same_sku() -> None:
    item = product()
    update = ProductUpdate(sku_code="Case-SKU")
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        get_by_profile_sku=AsyncMock(return_value=item),
        update=AsyncMock(return_value=item),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    assert await service.update_product(7, update) is item
    repository.update.assert_awaited_once_with(7, update)


async def test_update_rejects_missing_product_before_lifecycle_guard() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        has_orders=AsyncMock(),
        update=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductNotFoundError):
        await service.update_product(999, ProductUpdate())

    repository.has_orders.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_handles_disappearing_product() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=product()),
        has_orders=AsyncMock(return_value=False),
        update=AsyncMock(return_value=None),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductNotFoundError):
        await service.update_product(7, ProductUpdate(name="Renamed"))


async def test_delete_unused_product_succeeds() -> None:
    item = product()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_orders=AsyncMock(return_value=False),
        delete=AsyncMock(return_value=item),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    assert await service.delete_product(7) is item
    repository.has_orders.assert_awaited_once_with(7)
    repository.delete.assert_awaited_once_with(7)


async def test_delete_used_product_is_rejected_before_delete() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=product()),
        has_orders=AsyncMock(return_value=True),
        delete=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductInUseError):
        await service.delete_product(7)

    repository.delete.assert_not_awaited()


async def test_delete_missing_product_is_rejected_before_guard() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        has_orders=AsyncMock(),
        delete=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductNotFoundError):
        await service.delete_product(999)

    repository.has_orders.assert_not_awaited()
    repository.delete.assert_not_awaited()


async def test_delete_handles_disappearing_product() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=product()),
        has_orders=AsyncMock(return_value=False),
        delete=AsyncMock(return_value=None),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(ProductNotFoundError):
        await service.delete_product(7)
