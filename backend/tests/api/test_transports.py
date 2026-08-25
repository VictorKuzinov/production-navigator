import pytest
from httpx import AsyncClient, Response


def transport_payload(reference_rows: dict[str, str]) -> dict[str, object]:
    return {
        "transport_type_code": reference_rows["transport_type"],
        "transport_scope_code": reference_rows["transport_scope"],
        "transport_ownership_code": reference_rows[
            "transport_ownership_type"
        ],
        "payload_tons": 1.5,
        "body_volume_cube": 12.0,
        "has_refrigeration": True,
        "quantity": 2,
    }


async def create_transport(
    api_client: AsyncClient,
    profile_id: object,
    reference_rows: dict[str, str],
    **overrides: object,
) -> Response:
    payload = transport_payload(reference_rows)
    payload.update(overrides)
    return await api_client.post(
        f"/api/v1/enterprises/{profile_id}/transports",
        json=payload,
    )


async def test_transport_api_crud_patch_regressions_and_profile_isolation(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    profile_id = api_profile["id"]
    empty_list = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/transports"
    )
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    create_response = await create_transport(
        api_client,
        profile_id,
        reference_rows,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    transport_id = created["id"]
    assert created["profile_id"] == profile_id
    assert created["has_refrigeration"] is True

    other_profile_response = await api_client.post(
        "/api/v1/enterprises",
        json={
            "company_name": "Other transport API enterprise",
            "inn": "6671000004",
            "ogrn": "1069600000004",
        },
    )
    assert other_profile_response.status_code == 200
    other_profile_id = other_profile_response.json()["id"]
    other_create = await create_transport(
        api_client,
        other_profile_id,
        reference_rows,
        payload_tons=9.0,
    )
    assert other_create.status_code == 200

    list_response = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/transports"
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [transport_id]

    get_response = await api_client.get(f"/api/v1/transports/{transport_id}")
    assert get_response.status_code == 200
    assert get_response.json() == created

    false_response = await api_client.patch(
        f"/api/v1/transports/{transport_id}",
        json={
            "transport_type_code": reference_rows["other_transport_type"],
            "transport_scope_code": reference_rows["other_transport_scope"],
            "transport_ownership_code": reference_rows[
                "other_transport_ownership_type"
            ],
            "body_volume_cube": None,
            "has_refrigeration": False,
        },
    )
    assert false_response.status_code == 200
    false_state = false_response.json()
    assert false_state["transport_type_code"] == reference_rows[
        "other_transport_type"
    ]
    assert false_state["transport_scope_code"] == reference_rows[
        "other_transport_scope"
    ]
    assert false_state["transport_ownership_code"] == reference_rows[
        "other_transport_ownership_type"
    ]
    assert false_state["body_volume_cube"] is None
    assert false_state["has_refrigeration"] is False
    assert false_state["payload_tons"] == 1.5
    assert false_state["quantity"] == 2

    omitted_response = await api_client.patch(
        f"/api/v1/transports/{transport_id}",
        json={"payload_tons": 2.0},
    )
    assert omitted_response.status_code == 200
    assert omitted_response.json()["payload_tons"] == 2.0
    assert omitted_response.json()["has_refrigeration"] is False
    assert omitted_response.json()["body_volume_cube"] is None

    null_response = await api_client.patch(
        f"/api/v1/transports/{transport_id}",
        json={"has_refrigeration": None},
    )
    assert null_response.status_code == 200
    assert null_response.json()["has_refrigeration"] is None

    empty_patch = await api_client.patch(
        f"/api/v1/transports/{transport_id}",
        json={},
    )
    assert empty_patch.status_code == 200
    assert empty_patch.json() == null_response.json()

    delete_response = await api_client.delete(
        f"/api/v1/transports/{transport_id}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == transport_id

    after_delete = await api_client.get(f"/api/v1/transports/{transport_id}")
    second_delete = await api_client.delete(
        f"/api/v1/transports/{transport_id}"
    )
    assert after_delete.status_code == 404
    assert second_delete.status_code == 404


@pytest.mark.parametrize(
    "invalid_reference",
    [
        "transport_type_code",
        "transport_scope_code",
        "transport_ownership_code",
    ],
)
async def test_create_rejects_each_unknown_reference(
    invalid_reference: str,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    response = await create_transport(
        api_client,
        api_profile["id"],
        reference_rows,
        **{invalid_reference: "NO_SUCH_REFERENCE"},
    )

    assert response.status_code == 404


async def test_patch_rejects_unknown_replacement_reference(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    created = await create_transport(
        api_client,
        api_profile["id"],
        reference_rows,
    )
    assert created.status_code == 200

    response = await api_client.patch(
        f"/api/v1/transports/{created.json()['id']}",
        json={"transport_scope_code": "NO_SUCH_REFERENCE"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("payload_tons", 0),
        ("payload_tons", -1),
        ("body_volume_cube", 0),
        ("body_volume_cube", -1),
        ("quantity", 0),
    ],
)
async def test_create_rejects_invalid_transport_ranges(
    field_name: str,
    invalid_value: float | int,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    response = await create_transport(
        api_client,
        api_profile["id"],
        reference_rows,
        **{field_name: invalid_value},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field_name",
    [
        "transport_type_code",
        "transport_scope_code",
        "transport_ownership_code",
        "payload_tons",
        "quantity",
    ],
)
async def test_patch_rejects_null_for_non_nullable_fields(
    field_name: str,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    created = await create_transport(
        api_client,
        api_profile["id"],
        reference_rows,
    )
    assert created.status_code == 200

    response = await api_client.patch(
        f"/api/v1/transports/{created.json()['id']}",
        json={field_name: None},
    )

    assert response.status_code == 422


async def test_profile_and_item_not_found_errors_are_exposed_as_404(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    list_response = await api_client.get(
        "/api/v1/enterprises/999999/transports"
    )
    create_response = await create_transport(
        api_client,
        999999,
        reference_rows,
    )
    get_response = await api_client.get("/api/v1/transports/999999")
    patch_response = await api_client.patch(
        "/api/v1/transports/999999",
        json={},
    )
    delete_response = await api_client.delete("/api/v1/transports/999999")

    assert list_response.status_code == 404
    assert create_response.status_code == 404
    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
