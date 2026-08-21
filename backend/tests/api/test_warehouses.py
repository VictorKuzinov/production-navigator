from httpx import AsyncClient


async def test_warehouse_api_acceptance_flow(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    profile_id = api_profile["id"]
    list_response = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/warehouses"
    )
    assert list_response.status_code == 200
    assert list_response.json() == []

    create_response = await api_client.post(
        f"/api/v1/enterprises/{profile_id}/warehouses",
        json={
            "warehouse_type_code": reference_rows["warehouse_type"],
            "total_capacity_cube": 180.0,
            "max_load_sqm": 50.0,
            "temperature_control": False,
        },
    )
    assert create_response.status_code == 200
    warehouse = create_response.json()
    warehouse_id = warehouse["id"]

    get_response = await api_client.get(f"/api/v1/warehouses/{warehouse_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == warehouse_id

    clear_response = await api_client.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        json={"max_load_sqm": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["max_load_sqm"] is None
    assert clear_response.json()["total_capacity_cube"] == 180.0

    change_type_response = await api_client.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        json={"warehouse_type_code": reference_rows["other_warehouse_type"]},
    )
    assert change_type_response.status_code == 200
    assert (
        change_type_response.json()["warehouse_type_code"]
        == reference_rows["other_warehouse_type"]
    )
    assert change_type_response.json()["total_capacity_cube"] == 180.0
    assert change_type_response.json()["max_load_sqm"] is None

    invalid_reference = await api_client.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        json={"warehouse_type_code": "NO_SUCH_TYPE"},
    )
    assert invalid_reference.status_code == 404

    delete_response = await api_client.delete(
        f"/api/v1/warehouses/{warehouse_id}"
    )
    after_delete = await api_client.get(f"/api/v1/warehouses/{warehouse_id}")
    assert delete_response.status_code == 200
    assert after_delete.status_code == 404


async def test_patch_warehouse_rejects_null_warehouse_type_code(
    api_client: AsyncClient,
    api_warehouse: dict[str, object],
) -> None:
    response = await api_client.patch(
        f"/api/v1/warehouses/{api_warehouse['id']}",
        json={"warehouse_type_code": None},
    )

    assert response.status_code == 422


async def test_patch_warehouse_rejects_null_total_capacity(
    api_client: AsyncClient,
    api_warehouse: dict[str, object],
) -> None:
    response = await api_client.patch(
        f"/api/v1/warehouses/{api_warehouse['id']}",
        json={"total_capacity_cube": None},
    )

    assert response.status_code == 422


async def test_patch_warehouse_rejects_null_temperature_control(
    api_client: AsyncClient,
    api_warehouse: dict[str, object],
) -> None:
    response = await api_client.patch(
        f"/api/v1/warehouses/{api_warehouse['id']}",
        json={"temperature_control": None},
    )

    assert response.status_code == 422
