from httpx import AsyncClient


async def test_patch_production_facility_persists_changes(
    api_client: AsyncClient,
    api_profile: dict[str, object],
) -> None:
    create_response = await api_client.post(
        f"/api/v1/enterprises/{api_profile['id']}/facilities",
        json={
            "facility_name": "Facility update regression",
            "total_area": 300.0,
            "available_area": 120.0,
            "power_capacity": 180.0,
            "compressed_air": True,
            "water_supply": True,
        },
    )
    assert create_response.status_code == 200
    facility = create_response.json()
    facility_id = facility["id"]

    before_patch = await api_client.get(f"/api/v1/facilities/{facility_id}")
    assert before_patch.status_code == 200
    assert before_patch.json()["available_area"] == 120.0

    patch_response = await api_client.patch(
        f"/api/v1/facilities/{facility_id}",
        json={"available_area": 75.0},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["available_area"] == 75.0
    assert patch_response.json()["total_area"] == 300.0

    after_patch = await api_client.get(f"/api/v1/facilities/{facility_id}")
    assert after_patch.status_code == 200
    assert after_patch.json()["available_area"] == 75.0
