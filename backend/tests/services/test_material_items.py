from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.exceptions import (
    DuplicateMaterialItemError,
    InvalidMaterialItemError,
    MaterialFormNotFoundError,
    MaterialItemInUseError,
    MaterialItemNotFoundError,
    MaterialNotFoundError,
)
from app.schemas import MaterialItemCreate, MaterialItemUpdate
from app.services.material_items import MaterialItemService


def build_service(repository, materials, references) -> MaterialItemService:
    return MaterialItemService(repository, materials, references)


def create_data() -> MaterialItemCreate:
    return MaterialItemCreate(
        material_id=10,
        material_form_code="BAR_ROUND",
        dimension_1=20.0,
        unit_of_measure="kg",
    )


def material_item(**overrides: object) -> SimpleNamespace:
    values = {
        "id": 7,
        "material_id": 10,
        "material_form_code": "BAR_ROUND",
        "dimension_1": 20.0,
        "unit_of_measure": "kg",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def test_create_validates_references_and_duplicate_before_persisting() -> None:
    data = create_data()
    created = material_item()
    repository = SimpleNamespace(
        get_by_identity=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created),
    )
    materials = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(
        get_material_form_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, materials, references)
    calls = Mock()
    calls.attach_mock(materials.get_by_id, "material")
    calls.attach_mock(references.get_material_form_by_code, "form")
    calls.attach_mock(repository.get_by_identity, "duplicate")
    calls.attach_mock(repository.create, "create")

    result = await service.create_material_item(data)

    assert result is created
    assert calls.mock_calls == [
        call.material(10),
        call.form("BAR_ROUND"),
        call.duplicate(10, "BAR_ROUND", 20.0, "kg"),
        call.create(data),
    ]


async def test_create_rejects_unknown_material_before_form_lookup() -> None:
    repository = SimpleNamespace(
        get_by_identity=AsyncMock(),
        create=AsyncMock(),
    )
    materials = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    references = SimpleNamespace(get_material_form_by_code=AsyncMock())
    service = build_service(repository, materials, references)

    with pytest.raises(MaterialNotFoundError):
        await service.create_material_item(create_data())

    references.get_material_form_by_code.assert_not_awaited()
    repository.get_by_identity.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_unknown_material_form_before_duplicate() -> None:
    repository = SimpleNamespace(
        get_by_identity=AsyncMock(),
        create=AsyncMock(),
    )
    materials = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(get_material_form_by_code=AsyncMock(return_value=None))
    service = build_service(repository, materials, references)

    with pytest.raises(MaterialFormNotFoundError):
        await service.create_material_item(create_data())

    repository.get_by_identity.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_duplicate_with_null_dimension() -> None:
    data = MaterialItemCreate(
        material_id=10,
        material_form_code="BAR_ROUND",
        dimension_1=None,
        unit_of_measure="kg",
    )
    repository = SimpleNamespace(
        get_by_identity=AsyncMock(return_value=material_item(dimension_1=None)),
        create=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=object())),
        SimpleNamespace(get_material_form_by_code=AsyncMock(return_value=object())),
    )

    with pytest.raises(DuplicateMaterialItemError):
        await service.create_material_item(data)

    repository.get_by_identity.assert_awaited_once_with(
        10,
        "BAR_ROUND",
        None,
        "kg",
    )
    repository.create.assert_not_awaited()


async def test_get_and_list_delegate_to_global_repository() -> None:
    item = material_item()
    items = [item, material_item(id=8)]
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        list_material_items=AsyncMock(return_value=items),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    assert await service.get_material_item(7) is item
    assert await service.list_material_items() is items
    repository.get_by_id.assert_awaited_once_with(7)
    repository.list_material_items.assert_awaited_once_with()


async def test_get_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(MaterialItemNotFoundError):
        await service.get_material_item(999)


async def test_update_all_identity_fields_validates_resulting_state() -> None:
    item = material_item()
    update = MaterialItemUpdate(
        material_id=11,
        material_form_code="SHEET_PLATE",
        dimension_1=2.0,
        unit_of_measure="m2",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        get_by_identity=AsyncMock(return_value=None),
        update=AsyncMock(return_value=item),
    )
    materials = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(
        get_material_form_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, materials, references)

    assert await service.update_material_item(7, update) is item
    repository.has_products.assert_awaited_once_with(7)
    materials.get_by_id.assert_awaited_once_with(11)
    references.get_material_form_by_code.assert_awaited_once_with("SHEET_PLATE")
    repository.get_by_identity.assert_awaited_once_with(
        11,
        "SHEET_PLATE",
        2.0,
        "m2",
    )
    repository.update.assert_awaited_once_with(7, update)


async def test_update_used_item_rejects_identity_change_before_validation() -> None:
    item = material_item()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=True),
        get_by_identity=AsyncMock(),
        update=AsyncMock(),
    )
    materials = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_material_form_by_code=AsyncMock())
    service = build_service(repository, materials, references)

    with pytest.raises(MaterialItemInUseError):
        await service.update_material_item(
            7,
            MaterialItemUpdate(unit_of_measure="m"),
        )

    materials.get_by_id.assert_not_awaited()
    references.get_material_form_by_code.assert_not_awaited()
    repository.get_by_identity.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_used_item_allows_empty_no_op() -> None:
    item = material_item()
    update = MaterialItemUpdate()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(),
        get_by_identity=AsyncMock(),
        update=AsyncMock(return_value=item),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    assert await service.update_material_item(7, update) is item
    repository.has_products.assert_not_awaited()
    repository.get_by_identity.assert_not_awaited()
    repository.update.assert_awaited_once_with(7, update)


async def test_update_to_liquid_requires_explicit_dimension_clear() -> None:
    item = material_item(dimension_1=20.0)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        get_by_identity=AsyncMock(),
        update=AsyncMock(),
    )
    references = SimpleNamespace(
        get_material_form_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, SimpleNamespace(), references)

    with pytest.raises(InvalidMaterialItemError):
        await service.update_material_item(
            7,
            MaterialItemUpdate(material_form_code="LIQUID_CHEMICAL"),
        )

    repository.get_by_identity.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_to_liquid_accepts_explicit_dimension_clear() -> None:
    item = material_item(dimension_1=20.0)
    update = MaterialItemUpdate(
        material_form_code="LIQUID_CHEMICAL",
        dimension_1=None,
        unit_of_measure="l",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        get_by_identity=AsyncMock(return_value=None),
        update=AsyncMock(return_value=item),
    )
    references = SimpleNamespace(
        get_material_form_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, SimpleNamespace(), references)

    assert await service.update_material_item(7, update) is item
    repository.get_by_identity.assert_awaited_once_with(
        10,
        "LIQUID_CHEMICAL",
        None,
        "l",
    )
    repository.update.assert_awaited_once_with(7, update)


async def test_update_current_liquid_rejects_non_null_dimension() -> None:
    item = material_item(
        material_form_code="LIQUID_CHEMICAL",
        dimension_1=None,
        unit_of_measure="l",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        get_by_identity=AsyncMock(),
        update=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(InvalidMaterialItemError):
        await service.update_material_item(
            7,
            MaterialItemUpdate(dimension_1=1.0),
        )

    repository.get_by_identity.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_rejects_duplicate_resulting_identity() -> None:
    item = material_item()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        get_by_identity=AsyncMock(return_value=material_item(id=8)),
        update=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(DuplicateMaterialItemError):
        await service.update_material_item(
            7,
            MaterialItemUpdate(unit_of_measure="m"),
        )

    repository.update.assert_not_awaited()


async def test_update_rejects_missing_item_before_lifecycle_guard() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        has_products=AsyncMock(),
        update=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(MaterialItemNotFoundError):
        await service.update_material_item(999, MaterialItemUpdate())

    repository.has_products.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_delete_unused_item_succeeds() -> None:
    item = material_item()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=False),
        delete=AsyncMock(return_value=item),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    assert await service.delete_material_item(7) is item
    repository.has_products.assert_awaited_once_with(7)
    repository.delete.assert_awaited_once_with(7)


async def test_delete_used_item_is_rejected_before_delete() -> None:
    item = material_item()
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        has_products=AsyncMock(return_value=True),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(MaterialItemInUseError):
        await service.delete_material_item(7)

    repository.delete.assert_not_awaited()


async def test_delete_missing_item_is_rejected_before_guard() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        has_products=AsyncMock(),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(MaterialItemNotFoundError):
        await service.delete_material_item(999)

    repository.has_products.assert_not_awaited()
    repository.delete.assert_not_awaited()
