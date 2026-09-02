from datetime import datetime

import pytest
from httpx import AsyncClient


async def create_api_material(
    api_client: AsyncClient,
    group_code: str,
    grade_name: str = "Сталь 45",
) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/materials",
        json={
            "group_code": group_code,
            "grade_name": grade_name,
            "density": 7850.0,
        },
    )
    assert response.status_code == 200
    return response.json()


async def test_profile_creation_exposes_two_initial_unknown_sections(
    api_client: AsyncClient,
    api_profile: dict[str, object],
) -> None:
    response = await api_client.get(
        f"/api/v1/enterprises/{api_profile['id']}/capability-sections"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "profile_id": api_profile["id"],
            "section_code": "TECHNOLOGIES",
            "state": "UNKNOWN",
            "confirmed_at": None,
            "confirmed_by": None,
        },
        {
            "profile_id": api_profile["id"],
            "section_code": "MATERIALS",
            "state": "UNKNOWN",
            "confirmed_at": None,
            "confirmed_by": None,
        },
    ]


@pytest.mark.parametrize("state", ["SUPPORTED", "UNSUPPORTED", "UNKNOWN"])
async def test_technology_put_get_and_delete_support_explicit_states(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
    state: str,
) -> None:
    path = (
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities/"
        f"{reference_rows['technology_type']}"
    )
    response = await api_client.put(path, json={"state": state})

    assert response.status_code == 200
    assert response.json() == {
        "profile_id": api_profile["id"],
        "technology_code": reference_rows["technology_type"],
        "state": state,
    }

    listed = await api_client.get(
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities"
    )
    assert listed.status_code == 200
    assert listed.json() == [response.json()]

    deleted = await api_client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (await api_client.delete(path)).status_code == 204


@pytest.mark.parametrize(
    "payload",
    [{}, {"state": "NO_ASSERTION"}, {"state": "SUPPORTED", "version": 1}],
)
async def test_technology_put_rejects_missing_invalid_and_version_state(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
    payload: dict[str, object],
) -> None:
    response = await api_client.put(
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities/"
        f"{reference_rows['technology_type']}",
        json=payload,
    )
    assert response.status_code == 422


async def test_capability_routes_report_invalid_profile_and_references(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    invalid_profile = await api_client.put(
        "/api/v1/enterprises/999999/technology-capabilities/"
        f"{reference_rows['technology_type']}",
        json={"state": "SUPPORTED"},
    )
    invalid_technology = await api_client.put(
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities/"
        "NO_SUCH_TECHNOLOGY",
        json={"state": "SUPPORTED"},
    )
    invalid_group = await api_client.put(
        f"/api/v1/enterprises/{api_profile['id']}/material-capabilities/groups/"
        "NO_SUCH_GROUP",
        json={"state": "SUPPORTED"},
    )
    invalid_material = await api_client.put(
        f"/api/v1/enterprises/{api_profile['id']}/material-capabilities/materials/"
        "999999",
        json={"state": "SUPPORTED"},
    )

    assert invalid_profile.status_code == 404
    assert invalid_technology.status_code == 404
    assert invalid_group.status_code == 404
    assert invalid_material.status_code == 404


async def test_material_group_and_specific_routes_keep_distinct_targets(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    material = await create_api_material(
        api_client,
        reference_rows["material_group"],
    )
    group_path = (
        f"/api/v1/enterprises/{api_profile['id']}/material-capabilities/groups/"
        f"{reference_rows['material_group']}"
    )
    material_path = (
        f"/api/v1/enterprises/{api_profile['id']}/material-capabilities/materials/"
        f"{material['id']}"
    )

    group = await api_client.put(group_path, json={"state": "SUPPORTED"})
    specific = await api_client.put(material_path, json={"state": "UNKNOWN"})
    listed = await api_client.get(
        f"/api/v1/enterprises/{api_profile['id']}/material-capabilities"
    )

    assert group.status_code == 200
    assert group.json()["material_group_code"] == reference_rows["material_group"]
    assert group.json()["material_id"] is None
    assert specific.status_code == 200
    assert specific.json()["material_group_code"] is None
    assert specific.json()["material_id"] == material["id"]
    assert listed.status_code == 200
    assert listed.json() == [group.json(), specific.json()]

    assert (await api_client.delete(group_path)).status_code == 204
    assert (await api_client.delete(material_path)).status_code == 204
    assert (await api_client.delete(material_path)).status_code == 204


async def test_confirmation_is_explicit_trimmed_and_server_timestamped(
    api_client: AsyncClient,
    api_profile: dict[str, object],
) -> None:
    base = f"/api/v1/enterprises/{api_profile['id']}/capability-sections/MATERIALS"
    rejected_complete = await api_client.put(
        f"{base}/state",
        json={"state": "CONFIRMED_COMPLETE"},
    )
    blank = await api_client.put(
        f"{base}/confirmation",
        json={"confirmed_by": "   "},
    )
    client_timestamp = await api_client.put(
        f"{base}/confirmation",
        json={
            "confirmed_by": "operator",
            "confirmed_at": "2000-01-01T00:00:00Z",
        },
    )
    confirmed = await api_client.put(
        f"{base}/confirmation",
        json={"confirmed_by": "  operator-one  "},
    )

    assert rejected_complete.status_code == 422
    assert blank.status_code == 422
    assert client_timestamp.status_code == 422
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "CONFIRMED_COMPLETE"
    assert confirmed.json()["confirmed_by"] == "operator-one"
    first_timestamp = datetime.fromisoformat(confirmed.json()["confirmed_at"])

    reconfirmed = await api_client.put(
        f"{base}/confirmation",
        json={"confirmed_by": "operator-two"},
    )
    assert reconfirmed.status_code == 200
    assert reconfirmed.json()["confirmed_by"] == "operator-two"
    assert datetime.fromisoformat(reconfirmed.json()["confirmed_at"]) > first_timestamp

    reset = await api_client.put(f"{base}/state", json={"state": "UNKNOWN"})
    assert reset.status_code == 200
    assert reset.json()["confirmed_by"] is None
    assert reset.json()["confirmed_at"] is None


async def test_confirmed_section_is_invalidated_only_by_semantic_mutation(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    profile_id = api_profile["id"]
    section_path = (
        f"/api/v1/enterprises/{profile_id}/capability-sections/TECHNOLOGIES"
    )
    capability_path = (
        f"/api/v1/enterprises/{profile_id}/technology-capabilities/"
        f"{reference_rows['technology_type']}"
    )
    await api_client.put(capability_path, json={"state": "SUPPORTED"})
    confirmed = await api_client.put(
        f"{section_path}/confirmation",
        json={"confirmed_by": "operator"},
    )
    timestamp = confirmed.json()["confirmed_at"]

    same = await api_client.put(capability_path, json={"state": "SUPPORTED"})
    sections = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/capability-sections"
    )
    assert same.status_code == 200
    assert sections.json()[0]["state"] == "CONFIRMED_COMPLETE"
    assert sections.json()[0]["confirmed_at"] == timestamp

    changed = await api_client.put(capability_path, json={"state": "UNKNOWN"})
    sections = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/capability-sections"
    )
    assert changed.status_code == 200
    assert sections.json()[0]["state"] == "PARTIAL"
    assert sections.json()[0]["confirmed_at"] is None
    assert sections.json()[0]["confirmed_by"] is None


async def test_api_profile_isolation_for_capability_lists(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> None:
    second_response = await api_client.post(
        "/api/v1/enterprises",
        json={"company_name": "Second API profile", "inn": "6671000099"},
    )
    assert second_response.status_code == 200
    second = second_response.json()
    code = reference_rows["technology_type"]
    await api_client.put(
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities/{code}",
        json={"state": "SUPPORTED"},
    )

    second_list = await api_client.get(
        f"/api/v1/enterprises/{second['id']}/technology-capabilities"
    )
    second_delete = await api_client.delete(
        f"/api/v1/enterprises/{second['id']}/technology-capabilities/{code}"
    )
    first_list = await api_client.get(
        f"/api/v1/enterprises/{api_profile['id']}/technology-capabilities"
    )

    assert second_list.json() == []
    assert second_delete.status_code == 204
    assert len(first_list.json()) == 1
