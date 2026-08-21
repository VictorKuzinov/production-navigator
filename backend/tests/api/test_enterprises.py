from httpx import AsyncClient


async def test_enterprise_api_crud_preserves_optional_and_reference_fields(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    create_response = await api_client.post(
        "/api/v1/enterprises",
        json={
            "company_name": "Enterprise API lifecycle",
            "inn": "6671000020",
            "ogrn": "1069600000020",
            "website": "https://before.example.test",
            "employees_count": 18,
            "company_size_code": reference_rows["company_size"],
            "region_code": reference_rows["region"],
        },
    )
    assert create_response.status_code == 200
    profile = create_response.json()
    profile_id = profile["id"]
    assert profile["company_size_code"] == reference_rows["company_size"]
    assert profile["region_code"] == reference_rows["region"]

    list_response = await api_client.get("/api/v1/enterprises")
    get_response = await api_client.get(f"/api/v1/enterprises/{profile_id}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [profile_id]
    assert get_response.status_code == 200

    patch_response = await api_client.patch(
        f"/api/v1/enterprises/{profile_id}",
        json={
            "website": None,
            "employees_count": 24,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["website"] is None
    assert patch_response.json()["employees_count"] == 24
    assert patch_response.json()["company_name"] == "Enterprise API lifecycle"

    delete_response = await api_client.delete(
        f"/api/v1/enterprises/{profile_id}"
    )
    after_delete = await api_client.get(f"/api/v1/enterprises/{profile_id}")
    assert delete_response.status_code == 200
    assert after_delete.status_code == 404
