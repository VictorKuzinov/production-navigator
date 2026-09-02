from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.exceptions import (
    DuplicateMaterialError,
    MaterialGroupNotFoundError,
    MaterialInUseError,
    MaterialNotFoundError,
    MaterialReclassificationBlockedError,
)
from app.schemas import MaterialCreate, MaterialUpdate
from app.services.materials import MaterialService


def build_service(repository, references) -> MaterialService:
    return MaterialService(repository, references)


def create_data() -> MaterialCreate:
    return MaterialCreate(
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
        density=7850.0,
    )


async def test_create_validates_group_and_duplicate_before_persisting() -> None:
    data = create_data()
    created = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_group_and_grade=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, references)
    calls = Mock()
    calls.attach_mock(references.get_material_group_by_code, "group")
    calls.attach_mock(repository.get_by_group_and_grade, "duplicate")
    calls.attach_mock(repository.create, "create")

    result = await service.create_material(data)

    assert result is created
    assert calls.mock_calls == [
        call.group("STEEL_CARBON"),
        call.duplicate("STEEL_CARBON", "Сталь 45"),
        call.create(data),
    ]


async def test_create_rejects_unknown_material_group() -> None:
    repository = SimpleNamespace(
        get_by_group_and_grade=AsyncMock(),
        create=AsyncMock(),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, references)

    with pytest.raises(MaterialGroupNotFoundError):
        await service.create_material(create_data())

    repository.get_by_group_and_grade.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_duplicate_group_and_grade() -> None:
    repository = SimpleNamespace(
        get_by_group_and_grade=AsyncMock(
            return_value=SimpleNamespace(id=1)
        ),
        create=AsyncMock(),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, references)

    with pytest.raises(DuplicateMaterialError):
        await service.create_material(create_data())

    repository.create.assert_not_awaited()


async def test_get_returns_existing_material() -> None:
    material = SimpleNamespace(id=7)
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=material))
    service = build_service(repository, SimpleNamespace())

    assert await service.get_material(7) is material


async def test_get_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(repository, SimpleNamespace())

    with pytest.raises(MaterialNotFoundError):
        await service.get_material(999)


async def test_list_delegates_to_global_material_repository() -> None:
    materials = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    repository = SimpleNamespace(
        list_materials=AsyncMock(return_value=materials)
    )
    service = build_service(repository, SimpleNamespace())

    assert await service.list_materials() is materials
    repository.list_materials.assert_awaited_once_with()


async def test_update_group_validates_reference_and_resulting_unique_pair() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    update = MaterialUpdate(group_code="STEEL_ALLOY")
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        get_by_group_and_grade=AsyncMock(return_value=None),
        has_reclassification_capability_dependencies=AsyncMock(
            return_value=False
        ),
        update=AsyncMock(return_value=material),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, references)

    assert await service.update_material(10, update) is material
    references.get_material_group_by_code.assert_awaited_once_with(
        "STEEL_ALLOY"
    )
    repository.get_by_group_and_grade.assert_awaited_once_with(
        "STEEL_ALLOY",
        "Сталь 45",
    )
    repository.has_reclassification_capability_dependencies.assert_awaited_once_with(
        10,
        "STEEL_CARBON",
        "STEEL_ALLOY",
    )
    repository.update.assert_awaited_once_with(10, update)


async def test_update_grade_checks_resulting_unique_pair_without_group_lookup() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    update = MaterialUpdate(grade_name="Сталь 20")
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        get_by_group_and_grade=AsyncMock(return_value=None),
        update=AsyncMock(return_value=material),
    )
    references = SimpleNamespace(get_material_group_by_code=AsyncMock())
    service = build_service(repository, references)

    assert await service.update_material(10, update) is material
    references.get_material_group_by_code.assert_not_awaited()
    repository.get_by_group_and_grade.assert_awaited_once_with(
        "STEEL_CARBON",
        "Сталь 20",
    )


async def test_update_rejects_unknown_replacement_group() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        get_by_group_and_grade=AsyncMock(),
        update=AsyncMock(),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, references)

    with pytest.raises(MaterialGroupNotFoundError):
        await service.update_material(
            10,
            MaterialUpdate(group_code="NO_SUCH_GROUP"),
        )

    repository.get_by_group_and_grade.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_update_group_rejects_capability_resolution_dependency() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    update = MaterialUpdate(group_code="STEEL_ALLOY")
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        get_by_group_and_grade=AsyncMock(return_value=None),
        has_reclassification_capability_dependencies=AsyncMock(
            return_value=True
        ),
        update=AsyncMock(),
    )
    references = SimpleNamespace(
        get_material_group_by_code=AsyncMock(return_value=object())
    )
    service = build_service(repository, references)

    with pytest.raises(MaterialReclassificationBlockedError):
        await service.update_material(10, update)

    repository.update.assert_not_awaited()


async def test_update_rejects_duplicate_resulting_pair() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        get_by_group_and_grade=AsyncMock(
            return_value=SimpleNamespace(id=11)
        ),
        update=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace())

    with pytest.raises(DuplicateMaterialError):
        await service.update_material(
            10,
            MaterialUpdate(grade_name="Сталь 20"),
        )

    repository.update.assert_not_awaited()


async def test_update_preserves_density_presence_and_empty_patch_semantics() -> None:
    material = SimpleNamespace(
        id=10,
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        update=AsyncMock(return_value=material),
    )
    service = build_service(repository, SimpleNamespace())
    positive = MaterialUpdate(density=0.5)
    clear = MaterialUpdate(density=None)
    omitted = MaterialUpdate(grade_name="Сталь 40")
    empty = MaterialUpdate()
    repository.get_by_group_and_grade = AsyncMock(return_value=None)

    await service.update_material(10, positive)
    await service.update_material(10, clear)
    await service.update_material(10, omitted)
    await service.update_material(10, empty)

    assert positive.model_dump(exclude_unset=True) == {"density": 0.5}
    assert clear.model_dump(exclude_unset=True) == {"density": None}
    assert "density" not in omitted.model_fields_set
    assert empty.model_fields_set == set()
    assert repository.update.await_args_list == [
        call(10, positive),
        call(10, clear),
        call(10, omitted),
        call(10, empty),
    ]


async def test_update_raises_domain_not_found_before_validation() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        update=AsyncMock(),
    )
    references = SimpleNamespace(get_material_group_by_code=AsyncMock())
    service = build_service(repository, references)

    with pytest.raises(MaterialNotFoundError):
        await service.update_material(999, MaterialUpdate())

    references.get_material_group_by_code.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_delete_unused_material_succeeds() -> None:
    material = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        has_material_items=AsyncMock(return_value=False),
        has_profile_capabilities=AsyncMock(return_value=False),
        delete=AsyncMock(return_value=material),
    )
    service = build_service(repository, SimpleNamespace())

    assert await service.delete_material(10) is material
    repository.has_material_items.assert_awaited_once_with(10)
    repository.has_profile_capabilities.assert_awaited_once_with(10)
    repository.delete.assert_awaited_once_with(10)


async def test_delete_material_with_item_is_rejected_before_delete() -> None:
    material = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        has_material_items=AsyncMock(return_value=True),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace())

    with pytest.raises(MaterialInUseError):
        await service.delete_material(10)

    repository.delete.assert_not_awaited()


async def test_delete_material_with_profile_capability_is_rejected() -> None:
    material = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=material),
        has_material_items=AsyncMock(return_value=False),
        has_profile_capabilities=AsyncMock(return_value=True),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace())

    with pytest.raises(MaterialInUseError):
        await service.delete_material(10)

    repository.delete.assert_not_awaited()


async def test_delete_nonexistent_material_is_rejected_before_guard() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        has_material_items=AsyncMock(),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace())

    with pytest.raises(MaterialNotFoundError):
        await service.delete_material(999)

    repository.has_material_items.assert_not_awaited()
    repository.delete.assert_not_awaited()
