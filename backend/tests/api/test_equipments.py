from httpx import AsyncClient


async def test_equipment_api_crud_validates_references_and_updates_model_name(
    api_client: AsyncClient,
    api_facility: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    profile_id = api_facility["profile_id"]
    facility_id = api_facility["id"]
    create_response = await api_client.post(
        f"/api/v1/enterprises/{profile_id}/facilities/{facility_id}/equipment",
        json={
            "equipment_type_code": reference_rows["equipment_type"],
            "model_name": "API lathe",
            "cnc": True,
            "axes": 3,
            "quantity": 2,
        },
    )
    assert create_response.status_code == 200
    equipment = create_response.json()
    equipment_id = equipment["id"]
    assert equipment["model_name"] == "API lathe"

    list_response = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/facilities/{facility_id}/equipment"
    )
    get_response = await api_client.get(f"/api/v1/equipment/{equipment_id}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [equipment_id]
    assert get_response.status_code == 200

    patch_response = await api_client.patch(
        f"/api/v1/equipment/{equipment_id}",
        json={
            "equipment_type_code": reference_rows["other_equipment_type"],
            "model_name": "API mill",
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["model_name"] == "API mill"
    assert (
        patch_response.json()["equipment_type_code"]
        == reference_rows["other_equipment_type"]
    )
    assert patch_response.json()["quantity"] == 2

    delete_response = await api_client.delete(
        f"/api/v1/equipment/{equipment_id}"
    )
    after_delete = await api_client.get(f"/api/v1/equipment/{equipment_id}")
    assert delete_response.status_code == 200
    assert after_delete.status_code == 404


async def test_create_equipment_rejects_unknown_equipment_type(
    api_client: AsyncClient,
    api_facility: dict[str, object],
) -> None:
    response = await api_client.post(
        "/api/v1/enterprises/"
        f"{api_facility['profile_id']}/facilities/{api_facility['id']}/equipment",
        json={
            "equipment_type_code": "NO_SUCH_TYPE",
            "model_name": "Invalid equipment",
        },
    )

    assert response.status_code == 404
