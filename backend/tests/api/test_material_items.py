import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile, MaterialForm, Product, ProductType


async def create_material(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
    grade_name: str = "Сталь 45",
) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/materials",
        json={
            "group_code": reference_rows["material_group"],
            "grade_name": grade_name,
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_material_item(
    api_client: AsyncClient,
    parent_material_id: object,
    reference_rows: dict[str, str],
    **overrides: object,
) -> Response:
    payload: dict[str, object] = {
        "material_id": parent_material_id,
        "material_form_code": reference_rows["material_form"],
        "dimension_1": 20.0,
        "unit_of_measure": "kg",
    }
    payload.update(overrides)
    return await api_client.post("/api/v1/material-items", json=payload)


async def add_liquid_form(db_session: AsyncSession) -> None:
    db_session.add(
        MaterialForm(
            code="LIQUID_CHEMICAL",
            name_ru="Жидкий химический материал",
            ics_section="71.100.01",
            ref_system="Test",
            ref_code="LIQUID_CHEMICAL",
            description="Test fixture for MaterialItem form validation.",
        )
    )
    await db_session.commit()


async def test_material_item_api_global_crud_and_patch_presence_semantics(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    empty_list = await api_client.get("/api/v1/material-items")
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    material = await create_material(api_client, reference_rows)
    create_response = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    material_item_id = created["id"]
    assert created == {
        "id": material_item_id,
        "material_id": material["id"],
        "material_form_code": reference_rows["material_form"],
        "dimension_1": 20.0,
        "unit_of_measure": "kg",
    }
    assert "profile_id" not in created

    list_response = await api_client.get("/api/v1/material-items")
    get_response = await api_client.get(f"/api/v1/material-items/{material_item_id}")
    assert list_response.status_code == 200
    assert list_response.json() == [created]
    assert get_response.status_code == 200
    assert get_response.json() == created

    clear_response = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={"dimension_1": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["dimension_1"] is None
    assert clear_response.json()["unit_of_measure"] == "kg"

    omitted_response = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={"unit_of_measure": "m"},
    )
    assert omitted_response.status_code == 200
    assert omitted_response.json()["dimension_1"] is None
    assert omitted_response.json()["unit_of_measure"] == "m"

    empty_patch = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={},
    )
    assert empty_patch.status_code == 200
    assert empty_patch.json() == omitted_response.json()

    delete_response = await api_client.delete(
        f"/api/v1/material-items/{material_item_id}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == material_item_id
    assert (
        await api_client.get(f"/api/v1/material-items/{material_item_id}")
    ).status_code == 404


async def test_create_rejects_unknown_material_and_material_form(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    missing_material = await create_material_item(
        api_client,
        999999,
        reference_rows,
    )
    assert missing_material.status_code == 404
    assert missing_material.json() == {"detail": "Material 999999 not found."}

    material = await create_material(api_client, reference_rows)
    missing_form = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
        material_form_code="NO_SUCH_FORM",
    )
    assert missing_form.status_code == 404
    assert missing_form.json() == {"detail": "Material form NO_SUCH_FORM not found."}


@pytest.mark.parametrize(
    ("field_name", "value", "expected_detail"),
    [
        ("material_id", 999999, "Material 999999 not found."),
        (
            "material_form_code",
            "NO_SUCH_FORM",
            "Material form NO_SUCH_FORM not found.",
        ),
    ],
)
async def test_patch_rejects_unknown_replacement_reference(
    field_name: str,
    value: object,
    expected_detail: str,
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(api_client, reference_rows)
    created = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
    )
    assert created.status_code == 200

    response = await api_client.patch(
        f"/api/v1/material-items/{created.json()['id']}",
        json={field_name: value},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": expected_detail}


async def test_duplicate_precheck_treats_null_dimensions_as_equal(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(api_client, reference_rows)
    first = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
        dimension_1=None,
    )
    duplicate = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
        dimension_1=None,
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Material item with the same identity already exists."
    }


async def test_patch_rejects_duplicate_resulting_identity(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(api_client, reference_rows)
    first = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
        unit_of_measure="kg",
    )
    second = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
        unit_of_measure="m",
    )
    assert first.status_code == 200
    assert second.status_code == 200

    duplicate = await api_client.patch(
        f"/api/v1/material-items/{second.json()['id']}",
        json={"unit_of_measure": "kg"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Material item with the same identity already exists."
    }


@pytest.mark.parametrize(
    ("payload", "method"),
    [
        ({"dimension_1": 0}, "post"),
        ({"dimension_1": -1}, "post"),
        ({"unit_of_measure": "KG"}, "post"),
        ({"unit_of_measure": " kg"}, "post"),
        ({"unit_of_measure": "roll"}, "post"),
        ({"material_id": None}, "post"),
        ({"material_form_code": None}, "post"),
        ({"unit_of_measure": None}, "post"),
        ({"dimension_1": 0}, "patch"),
        ({"dimension_1": -1}, "patch"),
        ({"unit_of_measure": "KG"}, "patch"),
        ({"material_id": None}, "patch"),
        ({"material_form_code": None}, "patch"),
        ({"unit_of_measure": None}, "patch"),
        (
            {
                "material_form_code": "LIQUID_CHEMICAL",
                "dimension_1": 1,
            },
            "patch",
        ),
    ],
)
async def test_api_exposes_payload_validation_errors_as_422(
    payload: dict[str, object],
    method: str,
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(api_client, reference_rows)
    if method == "post":
        response = await create_material_item(
            api_client,
            material["id"],
            reference_rows,
            **payload,
        )
    else:
        created = await create_material_item(
            api_client,
            material["id"],
            reference_rows,
        )
        assert created.status_code == 200
        response = await api_client.patch(
            f"/api/v1/material-items/{created.json()['id']}",
            json=payload,
        )

    assert response.status_code == 422
    response_body = response.json()
    assert set(response_body) == {"detail"}
    assert isinstance(response_body["detail"], list)
    assert response_body["detail"]
    validation_error = response_body["detail"][0]
    assert {"type", "loc", "msg", "input"} <= validation_error.keys()
    assert validation_error["loc"][0] == "body"


async def test_transition_to_liquid_requires_explicit_dimension_clear(
    api_client: AsyncClient,
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    await add_liquid_form(db_session)
    material = await create_material(api_client, reference_rows)
    created = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
    )
    assert created.status_code == 200
    material_item_id = created.json()["id"]

    omitted_clear = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={"material_form_code": "LIQUID_CHEMICAL"},
    )
    explicit_clear = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={
            "material_form_code": "LIQUID_CHEMICAL",
            "dimension_1": None,
            "unit_of_measure": "l",
        },
    )

    assert omitted_clear.status_code == 422
    assert omitted_clear.json() == {
        "detail": "dimension_1 must be null for LIQUID_CHEMICAL."
    }
    assert explicit_clear.status_code == 200
    assert explicit_clear.json()["material_form_code"] == "LIQUID_CHEMICAL"
    assert explicit_clear.json()["dimension_1"] is None
    assert explicit_clear.json()["unit_of_measure"] == "l"


async def test_missing_item_errors_and_profile_scoped_route_are_404(
    api_client: AsyncClient,
) -> None:
    get_response = await api_client.get("/api/v1/material-items/999999")
    patch_response = await api_client.patch(
        "/api/v1/material-items/999999",
        json={},
    )
    delete_response = await api_client.delete("/api/v1/material-items/999999")
    profile_route = await api_client.get("/api/v1/enterprises/1/material-items")

    assert get_response.status_code == 404
    assert get_response.json() == {"detail": "Material item 999999 not found."}
    assert patch_response.status_code == 404
    assert patch_response.json() == {"detail": "Material item 999999 not found."}
    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "Material item 999999 not found."}
    assert profile_route.status_code == 404


async def test_used_item_is_immutable_and_cannot_be_deleted(
    api_client: AsyncClient,
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    material = await create_material(api_client, reference_rows)
    created = await create_material_item(
        api_client,
        material["id"],
        reference_rows,
    )
    assert created.status_code == 200
    material_item_id = created.json()["id"]

    product_type = ProductType(
        code="API_TEST_PRODUCT_TYPE",
        name_ru="Тестовый тип продукции API",
        ics_section="25.000.00",
        ref_system="Test",
        ref_code="API_TEST_PRODUCT_TYPE",
        description="Test fixture for MaterialItem lifecycle API.",
    )
    product = Product(
        profile_id=enterprise_row.id,
        product_type_code=product_type.code,
        material_item_id=material_item_id,
        sku_code="API-TEST-SKU",
        name="Тестовое изделие API",
        weight_net=1.0,
    )
    db_session.add_all([product_type, product])
    await db_session.commit()

    changed = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={"unit_of_measure": "m"},
    )
    empty = await api_client.patch(
        f"/api/v1/material-items/{material_item_id}",
        json={},
    )
    deleted = await api_client.delete(f"/api/v1/material-items/{material_item_id}")
    persisted = await api_client.get(f"/api/v1/material-items/{material_item_id}")

    assert changed.status_code == 409
    assert changed.json() == {
        "detail": (
            f"Material item {material_item_id} is used by products "
            "and cannot be changed."
        )
    }
    assert empty.status_code == 200
    assert deleted.status_code == 409
    assert deleted.json() == {
        "detail": f"Material item {material_item_id} is used by products."
    }
    assert persisted.status_code == 200
    assert persisted.json()["unit_of_measure"] == "kg"
