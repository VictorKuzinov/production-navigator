from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    TransportNotFoundError,
    TransportOwnershipTypeNotFoundError,
    TransportScopeNotFoundError,
    TransportTypeNotFoundError,
)
from app.schemas import TransportCreate, TransportUpdate
from app.services.transports import TransportService


def build_service(repository, enterprises, references) -> TransportService:
    return TransportService(repository, enterprises, references)


def create_data() -> TransportCreate:
    return TransportCreate(
        transport_type_code="LIGHT_COMMERCIAL",
        transport_scope_code="REGIONAL",
        transport_ownership_code="PNC_OWN_OWNED",
        payload_tons=1.5,
        body_volume_cube=12.0,
        has_refrigeration=True,
        quantity=2,
    )


def reference_repository():
    return SimpleNamespace(
        get_transport_type_by_code=AsyncMock(return_value=object()),
        get_transport_scope_by_code=AsyncMock(return_value=object()),
        get_transport_ownership_type_by_code=AsyncMock(
            return_value=object()
        ),
    )


async def test_create_validates_profile_and_references_in_approved_order() -> None:
    data = create_data()
    created = SimpleNamespace(id=10, profile_id=7)
    repository = SimpleNamespace(create=AsyncMock(return_value=created))
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = reference_repository()
    service = build_service(repository, enterprises, references)
    calls = Mock()
    calls.attach_mock(enterprises.get_by_id, "profile")
    calls.attach_mock(references.get_transport_type_by_code, "transport_type")
    calls.attach_mock(references.get_transport_scope_by_code, "transport_scope")
    calls.attach_mock(
        references.get_transport_ownership_type_by_code,
        "transport_ownership_type",
    )
    calls.attach_mock(repository.create, "create")

    result = await service.create_transport(7, data)

    assert result is created
    assert calls.mock_calls == [
        call.profile(7),
        call.transport_type("LIGHT_COMMERCIAL"),
        call.transport_scope("REGIONAL"),
        call.transport_ownership_type("PNC_OWN_OWNED"),
        call.create(7, data),
    ]


async def test_create_requires_existing_profile_before_reference_lookup() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    references = reference_repository()
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        references,
    )

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create_transport(999, create_data())

    references.get_transport_type_by_code.assert_not_awaited()
    references.get_transport_scope_by_code.assert_not_awaited()
    references.get_transport_ownership_type_by_code.assert_not_awaited()
    repository.create.assert_not_awaited()


@pytest.mark.parametrize(
    ("missing_reference", "expected_error"),
    [
        ("transport_type", TransportTypeNotFoundError),
        ("transport_scope", TransportScopeNotFoundError),
        ("transport_ownership_type", TransportOwnershipTypeNotFoundError),
    ],
)
async def test_create_rejects_each_unknown_reference_in_validation_order(
    missing_reference: str,
    expected_error: type[Exception],
) -> None:
    lookup_names = {
        "transport_type": "get_transport_type_by_code",
        "transport_scope": "get_transport_scope_by_code",
        "transport_ownership_type": (
            "get_transport_ownership_type_by_code"
        ),
    }
    references = reference_repository()
    getattr(references, lookup_names[missing_reference]).return_value = None
    repository = SimpleNamespace(create=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=object())),
        references,
    )

    with pytest.raises(expected_error):
        await service.create_transport(7, create_data())

    repository.create.assert_not_awaited()
    if missing_reference == "transport_type":
        references.get_transport_scope_by_code.assert_not_awaited()
        references.get_transport_ownership_type_by_code.assert_not_awaited()
    elif missing_reference == "transport_scope":
        references.get_transport_type_by_code.assert_awaited_once()
        references.get_transport_ownership_type_by_code.assert_not_awaited()
    else:
        references.get_transport_type_by_code.assert_awaited_once()
        references.get_transport_scope_by_code.assert_awaited_once()


async def test_list_checks_profile_and_delegates_exact_profile_id() -> None:
    own_rows = [SimpleNamespace(id=1, profile_id=7)]
    repository = SimpleNamespace(
        list_by_profile=AsyncMock(return_value=own_rows)
    )
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    service = build_service(repository, enterprises, SimpleNamespace())

    result = await service.list_transports(7)

    assert result is own_rows
    enterprises.get_by_id.assert_awaited_once_with(7)
    repository.list_by_profile.assert_awaited_once_with(7)


async def test_list_rejects_missing_profile() -> None:
    repository = SimpleNamespace(list_by_profile=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        SimpleNamespace(),
    )

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.list_transports(999)

    repository.list_by_profile.assert_not_awaited()


async def test_get_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(TransportNotFoundError):
        await service.get_transport(999)


async def test_update_normal_fields_skips_reference_lookups() -> None:
    transport = SimpleNamespace(id=10, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=transport),
        update=AsyncMock(return_value=transport),
    )
    references = reference_repository()
    service = build_service(repository, SimpleNamespace(), references)
    update = TransportUpdate(payload_tons=2.5, quantity=3)

    result = await service.update_transport(10, update)

    assert result is transport
    references.get_transport_type_by_code.assert_not_awaited()
    references.get_transport_scope_by_code.assert_not_awaited()
    references.get_transport_ownership_type_by_code.assert_not_awaited()
    repository.update.assert_awaited_once_with(10, update)


@pytest.mark.parametrize(
    ("field_name", "replacement_code", "lookup_name"),
    [
        (
            "transport_type_code",
            "HEAVY_TRUCK",
            "get_transport_type_by_code",
        ),
        (
            "transport_scope_code",
            "NATIONAL",
            "get_transport_scope_by_code",
        ),
        (
            "transport_ownership_code",
            "PNC_OWN_LEASED",
            "get_transport_ownership_type_by_code",
        ),
    ],
)
async def test_update_validates_each_replacement_reference(
    field_name: str,
    replacement_code: str,
    lookup_name: str,
) -> None:
    transport = SimpleNamespace(id=10, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=transport),
        update=AsyncMock(return_value=transport),
    )
    references = reference_repository()
    service = build_service(repository, SimpleNamespace(), references)
    update = TransportUpdate(**{field_name: replacement_code})

    result = await service.update_transport(10, update)

    assert result is transport
    getattr(references, lookup_name).assert_awaited_once_with(replacement_code)
    repository.update.assert_awaited_once_with(10, update)


@pytest.mark.parametrize(
    ("field_name", "lookup_name", "expected_error"),
    [
        (
            "transport_type_code",
            "get_transport_type_by_code",
            TransportTypeNotFoundError,
        ),
        (
            "transport_scope_code",
            "get_transport_scope_by_code",
            TransportScopeNotFoundError,
        ),
        (
            "transport_ownership_code",
            "get_transport_ownership_type_by_code",
            TransportOwnershipTypeNotFoundError,
        ),
    ],
)
async def test_update_rejects_each_unknown_replacement_reference(
    field_name: str,
    lookup_name: str,
    expected_error: type[Exception],
) -> None:
    transport = SimpleNamespace(id=10, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=transport),
        update=AsyncMock(),
    )
    references = reference_repository()
    getattr(references, lookup_name).return_value = None
    service = build_service(repository, SimpleNamespace(), references)

    with pytest.raises(expected_error):
        await service.update_transport(
            10,
            TransportUpdate(**{field_name: "NO_SUCH_REFERENCE"}),
        )

    repository.update.assert_not_awaited()


async def test_update_preserves_false_null_omitted_and_empty_patch_semantics() -> None:
    transport = SimpleNamespace(
        id=10,
        profile_id=7,
    )
    false_result = SimpleNamespace(id=10, has_refrigeration=False)
    null_result = SimpleNamespace(
        id=10,
        body_volume_cube=None,
        has_refrigeration=None,
    )
    omitted_result = SimpleNamespace(id=10, payload_tons=2.0)
    empty_result = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=transport),
        update=AsyncMock(
            side_effect=[
                false_result,
                null_result,
                omitted_result,
                empty_result,
            ]
        ),
    )
    references = reference_repository()
    service = build_service(repository, SimpleNamespace(), references)
    false_update = TransportUpdate(has_refrigeration=False)
    null_update = TransportUpdate(
        body_volume_cube=None,
        has_refrigeration=None,
    )
    omitted_update = TransportUpdate(payload_tons=2.0)
    empty_update = TransportUpdate()

    assert await service.update_transport(10, false_update) is false_result
    assert await service.update_transport(10, null_update) is null_result
    assert await service.update_transport(10, omitted_update) is omitted_result
    assert await service.update_transport(10, empty_update) is empty_result

    assert false_update.model_fields_set == {"has_refrigeration"}
    assert false_update.has_refrigeration is False
    assert null_update.model_fields_set == {
        "body_volume_cube",
        "has_refrigeration",
    }
    assert null_update.body_volume_cube is None
    assert null_update.has_refrigeration is None
    assert omitted_update.model_fields_set == {"payload_tons"}
    assert "body_volume_cube" not in omitted_update.model_fields_set
    assert "has_refrigeration" not in omitted_update.model_fields_set
    assert empty_update.model_fields_set == set()
    assert repository.get_by_id.await_args_list == [
        call(10),
        call(10),
        call(10),
        call(10),
    ]
    assert repository.update.await_args_list == [
        call(10, false_update),
        call(10, null_update),
        call(10, omitted_update),
        call(10, empty_update),
    ]
    references.get_transport_type_by_code.assert_not_awaited()
    references.get_transport_scope_by_code.assert_not_awaited()
    references.get_transport_ownership_type_by_code.assert_not_awaited()


async def test_update_raises_domain_not_found() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        update=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(TransportNotFoundError):
        await service.update_transport(999, TransportUpdate())

    repository.update.assert_not_awaited()


async def test_delete_returns_deleted_transport() -> None:
    transport = SimpleNamespace(id=10, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=transport),
        delete=AsyncMock(return_value=transport),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    result = await service.delete_transport(10)

    assert result is transport
    repository.delete.assert_awaited_once_with(10)


async def test_delete_raises_domain_not_found() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        delete=AsyncMock(),
    )
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(TransportNotFoundError):
        await service.delete_transport(999)

    repository.delete.assert_not_awaited()
