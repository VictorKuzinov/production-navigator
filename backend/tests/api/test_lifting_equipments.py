import pytest
from httpx import AsyncClient


async def test_lifting_equipment_api_crud_and_all_location_combinations(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    api_facility: dict[str, object],
    api_warehouse: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    profile_id = api_profile["id"]
    facility_id = api_facility["id"]
    warehouse_id = api_warehouse["id"]
    location_payloads = [
        {"facility_id": facility_id},
        {"warehouse_id": warehouse_id},
        {"facility_id": facility_id, "warehouse_id": warehouse_id},
        {},
    ]
    created_items = []

    for index, location_payload in enumerate(location_payloads, start=1):
        response = await api_client.post(
            f"/api/v1/enterprises/{profile_id}/lifting-equipment",
            json={
                "crane_type_code": reference_rows["crane_type"],
                "load_capacity_tons": 5.0 + index,
                "max_lift_height": 6.0,
                "quantity": index,
                **location_payload,
            },
        )
        assert response.status_code == 200
        item = response.json()
        assert item["facility_id"] == location_payload.get("facility_id")
        assert item["warehouse_id"] == location_payload.get("warehouse_id")
        created_items.append(item)

    other_profile_response = await api_client.post(
        "/api/v1/enterprises",
        json={
            "company_name": "Listing-isolation enterprise",
            "inn": "6671000003",
            "ogrn": "1069600000003",
        },
    )
    assert other_profile_response.status_code == 200
    other_profile_id = other_profile_response.json()["id"]
    other_item_response = await api_client.post(
        f"/api/v1/enterprises/{other_profile_id}/lifting-equipment",
        json={
            "crane_type_code": reference_rows["crane_type"],
            "load_capacity_tons": 9.0,
        },
    )
    assert other_item_response.status_code == 200

    list_response = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/lifting-equipment"
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [
        item["id"] for item in created_items
    ]

    for item in created_items:
        get_response = await api_client.get(f"/api/v1/lifting-equipment/{item['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == item["id"]

    target = created_items[-1]
    set_locations = await api_client.patch(
        f"/api/v1/lifting-equipment/{target['id']}",
        json={
            "crane_type_code": reference_rows["other_crane_type"],
            "facility_id": facility_id,
            "warehouse_id": warehouse_id,
        },
    )
    assert set_locations.status_code == 200
    assert set_locations.json()["facility_id"] == facility_id
    assert set_locations.json()["warehouse_id"] == warehouse_id
    assert set_locations.json()["crane_type_code"] == reference_rows["other_crane_type"]
    assert set_locations.json()["load_capacity_tons"] == target["load_capacity_tons"]
    assert set_locations.json()["quantity"] == target["quantity"]

    replacement_facility_response = await api_client.post(
        f"/api/v1/enterprises/{profile_id}/facilities",
        json={
            "facility_name": "Replacement API facility",
            "total_area": 260.0,
            "available_area": 95.0,
        },
    )
    assert replacement_facility_response.status_code == 200
    replacement_facility_id = replacement_facility_response.json()["id"]

    replacement_warehouse_response = await api_client.post(
        f"/api/v1/enterprises/{profile_id}/warehouses",
        json={
            "warehouse_type_code": reference_rows["other_warehouse_type"],
            "total_capacity_cube": 140.0,
        },
    )
    assert replacement_warehouse_response.status_code == 200
    replacement_warehouse_id = replacement_warehouse_response.json()["id"]

    replace_facility = await api_client.patch(
        f"/api/v1/lifting-equipment/{target['id']}",
        json={"facility_id": replacement_facility_id},
    )
    assert replace_facility.status_code == 200
    assert replace_facility.json()["facility_id"] == replacement_facility_id
    assert replace_facility.json()["warehouse_id"] == warehouse_id

    after_facility_replacement = await api_client.get(
        f"/api/v1/lifting-equipment/{target['id']}"
    )
    assert after_facility_replacement.status_code == 200
    assert after_facility_replacement.json()["facility_id"] == replacement_facility_id
    assert after_facility_replacement.json()["warehouse_id"] == warehouse_id

    replace_warehouse = await api_client.patch(
        f"/api/v1/lifting-equipment/{target['id']}",
        json={"warehouse_id": replacement_warehouse_id},
    )
    assert replace_warehouse.status_code == 200
    assert replace_warehouse.json()["facility_id"] == replacement_facility_id
    assert replace_warehouse.json()["warehouse_id"] == replacement_warehouse_id

    after_warehouse_replacement = await api_client.get(
        f"/api/v1/lifting-equipment/{target['id']}"
    )
    assert after_warehouse_replacement.status_code == 200
    assert after_warehouse_replacement.json()["facility_id"] == replacement_facility_id
    assert (
        after_warehouse_replacement.json()["warehouse_id"] == replacement_warehouse_id
    )

    clear_locations = await api_client.patch(
        f"/api/v1/lifting-equipment/{target['id']}",
        json={
            "facility_id": None,
            "warehouse_id": None,
            "max_lift_height": None,
        },
    )
    assert clear_locations.status_code == 200
    assert clear_locations.json()["facility_id"] is None
    assert clear_locations.json()["warehouse_id"] is None
    assert clear_locations.json()["max_lift_height"] is None
    assert clear_locations.json()["quantity"] == target["quantity"]

    delete_response = await api_client.delete(
        f"/api/v1/lifting-equipment/{target['id']}"
    )
    after_delete = await api_client.get(f"/api/v1/lifting-equipment/{target['id']}")
    assert delete_response.status_code == 200
    assert after_delete.status_code == 404


@pytest.mark.parametrize(
    "invalid_kind",
    ["crane_type", "facility", "warehouse"],
)
async def test_create_rejects_unknown_references(
    invalid_kind: str,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    payload = {
        "crane_type_code": reference_rows["crane_type"],
        "load_capacity_tons": 5.0,
    }
    if invalid_kind == "crane_type":
        payload["crane_type_code"] = "NO_SUCH_TYPE"
    elif invalid_kind == "facility":
        payload["facility_id"] = 999999
    else:
        payload["warehouse_id"] = 999999

    response = await api_client.post(
        f"/api/v1/enterprises/{api_profile['id']}/lifting-equipment",
        json=payload,
    )

    assert response.status_code == 404


async def test_create_rejects_locations_owned_by_another_profile(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    other_profile_response = await api_client.post(
        "/api/v1/enterprises",
        json={
            "company_name": "Other API enterprise",
            "inn": "6671000002",
            "ogrn": "1069600000002",
        },
    )
    assert other_profile_response.status_code == 200
    other_profile_id = other_profile_response.json()["id"]

    other_facility_response = await api_client.post(
        f"/api/v1/enterprises/{other_profile_id}/facilities",
        json={
            "facility_name": "Other facility",
            "total_area": 100.0,
            "available_area": 50.0,
        },
    )
    assert other_facility_response.status_code == 200

    other_warehouse_response = await api_client.post(
        f"/api/v1/enterprises/{other_profile_id}/warehouses",
        json={
            "warehouse_type_code": reference_rows["warehouse_type"],
            "total_capacity_cube": 100.0,
        },
    )
    assert other_warehouse_response.status_code == 200

    location_payloads = [
        {"facility_id": other_facility_response.json()["id"]},
        {"warehouse_id": other_warehouse_response.json()["id"]},
    ]
    for location_payload in location_payloads:
        response = await api_client.post(
            f"/api/v1/enterprises/{api_profile['id']}/lifting-equipment",
            json={
                "crane_type_code": reference_rows["crane_type"],
                "load_capacity_tons": 5.0,
                **location_payload,
            },
        )
        assert response.status_code == 404


@pytest.mark.parametrize(
    "field_name",
    ["crane_type_code", "load_capacity_tons", "quantity"],
)
async def test_patch_rejects_null_for_non_nullable_fields(
    field_name: str,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    create_response = await api_client.post(
        f"/api/v1/enterprises/{api_profile['id']}/lifting-equipment",
        json={
            "crane_type_code": reference_rows["crane_type"],
            "load_capacity_tons": 5.0,
            "quantity": 2,
        },
    )
    assert create_response.status_code == 200

    response = await api_client.patch(
        f"/api/v1/lifting-equipment/{create_response.json()['id']}",
        json={field_name: None},
    )

    assert response.status_code == 422
