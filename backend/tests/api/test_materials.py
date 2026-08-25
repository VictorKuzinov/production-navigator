import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaterialItem


async def create_material(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
    **overrides: object,
) -> Response:
    payload: dict[str, object] = {
        "group_code": reference_rows["material_group"],
        "grade_name": "Сталь 45",
        "density": 7850.0,
    }
    payload.update(overrides)
    return await api_client.post("/api/v1/materials", json=payload)


async def test_material_api_global_crud_and_patch_presence_semantics(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    empty_list = await api_client.get("/api/v1/materials")
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    create_response = await create_material(api_client, reference_rows)
    assert create_response.status_code == 200
    created = create_response.json()
    material_id = created["id"]
    assert created == {
        "id": material_id,
        "group_code": reference_rows["material_group"],
        "grade_name": "Сталь 45",
        "density": 7850.0,
    }
    assert "profile_id" not in created

    list_response = await api_client.get("/api/v1/materials")
    get_response = await api_client.get(f"/api/v1/materials/{material_id}")
    assert list_response.status_code == 200
    assert list_response.json() == [created]
    assert get_response.status_code == 200
    assert get_response.json() == created

    change_response = await api_client.patch(
        f"/api/v1/materials/{material_id}",
        json={
            "group_code": reference_rows["other_material_group"],
            "grade_name": "40Х",
            "density": 7800.0,
        },
    )
    assert change_response.status_code == 200
    changed = change_response.json()
    assert changed["group_code"] == reference_rows["other_material_group"]
    assert changed["grade_name"] == "40Х"
    assert changed["density"] == 7800.0

    clear_response = await api_client.patch(
        f"/api/v1/materials/{material_id}",
        json={"density": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["density"] is None
    assert clear_response.json()["grade_name"] == "40Х"

    omitted_response = await api_client.patch(
        f"/api/v1/materials/{material_id}",
        json={"grade_name": "40Х ГОСТ"},
    )
    assert omitted_response.status_code == 200
    assert omitted_response.json()["density"] is None

    empty_patch = await api_client.patch(
        f"/api/v1/materials/{material_id}",
        json={},
    )
    assert empty_patch.status_code == 200
    assert empty_patch.json() == omitted_response.json()

    delete_response = await api_client.delete(
        f"/api/v1/materials/{material_id}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == material_id
    assert (
        await api_client.get(f"/api/v1/materials/{material_id}")
    ).status_code == 404


async def test_material_api_rejects_unknown_group_on_create_and_patch(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    create_response = await create_material(
        api_client,
        reference_rows,
        group_code="NO_SUCH_GROUP",
    )
    assert create_response.status_code == 404

    created = await create_material(api_client, reference_rows)
    assert created.status_code == 200
    patch_response = await api_client.patch(
        f"/api/v1/materials/{created.json()['id']}",
        json={"group_code": "NO_SUCH_GROUP"},
    )
    assert patch_response.status_code == 404


async def test_material_api_rejects_duplicate_create_and_resulting_patch(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    first = await create_material(api_client, reference_rows)
    assert first.status_code == 200

    duplicate = await create_material(api_client, reference_rows)
    assert duplicate.status_code == 409

    second = await create_material(
        api_client,
        reference_rows,
        grade_name="Сталь 20",
    )
    assert second.status_code == 200
    patch_duplicate = await api_client.patch(
        f"/api/v1/materials/{second.json()['id']}",
        json={"grade_name": "Сталь 45"},
    )
    assert patch_duplicate.status_code == 409


@pytest.mark.parametrize(
    ("payload", "method"),
    [
        ({"density": 0}, "post"),
        ({"density": -1}, "post"),
        ({"grade_name": ""}, "post"),
        ({"grade_name": "   "}, "post"),
        ({"group_code": None}, "post"),
        ({"grade_name": None}, "post"),
        ({"density": 0}, "patch"),
        ({"density": -1}, "patch"),
        ({"group_code": None}, "patch"),
        ({"grade_name": None}, "patch"),
        ({"grade_name": "\t"}, "patch"),
    ],
)
async def test_material_api_exposes_validation_errors_as_422(
    payload: dict[str, object],
    method: str,
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    if method == "post":
        response = await create_material(
            api_client,
            reference_rows,
            **payload,
        )
    else:
        created = await create_material(api_client, reference_rows)
        assert created.status_code == 200
        response = await api_client.patch(
            f"/api/v1/materials/{created.json()['id']}",
            json=payload,
        )

    assert response.status_code == 422


async def test_material_api_returns_404_for_missing_items_and_no_profile_route(
    api_client: AsyncClient,
) -> None:
    get_response = await api_client.get("/api/v1/materials/999999")
    patch_response = await api_client.patch(
        "/api/v1/materials/999999",
        json={},
    )
    delete_response = await api_client.delete("/api/v1/materials/999999")
    profile_route = await api_client.get(
        "/api/v1/enterprises/1/materials"
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert profile_route.status_code == 404


async def test_material_api_delete_guard_preserves_material_and_item(
    api_client: AsyncClient,
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    created = await create_material(api_client, reference_rows)
    assert created.status_code == 200
    material_id = created.json()["id"]
    item = MaterialItem(
        material_id=material_id,
        material_form_code=reference_rows["material_form"],
        dimension_1=20.0,
        unit_of_measure="kg",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    delete_response = await api_client.delete(
        f"/api/v1/materials/{material_id}"
    )

    assert delete_response.status_code == 409
    assert (
        await api_client.get(f"/api/v1/materials/{material_id}")
    ).status_code == 200
    assert await db_session.get(MaterialItem, item.id) is not None
