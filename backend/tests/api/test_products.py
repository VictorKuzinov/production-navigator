from datetime import date

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Industry, OrderType, ProductionOrder, ProductType


async def add_product_type(
    db_session: AsyncSession,
    code: str = "FINISHED_GOOD",
) -> str:
    db_session.add(
        ProductType(
            code=code,
            name_ru="Готовое изделие",
            ics_section="25.000.00",
            ref_system="Test",
            ref_code=code,
            description="Test fixture for Product API.",
        )
    )
    await db_session.commit()
    return code


async def create_material_item(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> dict[str, object]:
    material_response = await api_client.post(
        "/api/v1/materials",
        json={
            "group_code": reference_rows["material_group"],
            "grade_name": "Сталь Product API",
        },
    )
    assert material_response.status_code == 200
    material = material_response.json()

    item_response = await api_client.post(
        "/api/v1/material-items",
        json={
            "material_id": material["id"],
            "material_form_code": reference_rows["material_form"],
            "dimension_1": 20.0,
            "unit_of_measure": "kg",
        },
    )
    assert item_response.status_code == 200
    return item_response.json()


def product_payload(
    default_product_type_code: object,
    default_material_item_id: object,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "product_type_code": default_product_type_code,
        "material_item_id": default_material_item_id,
        "sku_code": "Case-SKU",
        "name": "Тестовое изделие",
        "weight_net": 12.5,
        "required_it_grade": 8,
        "required_ra": 1.6,
    }
    payload.update(overrides)
    return payload


async def create_product(
    api_client: AsyncClient,
    profile_id: object,
    default_product_type_code: object,
    default_material_item_id: object,
    **overrides: object,
) -> Response:
    return await api_client.post(
        f"/api/v1/enterprises/{profile_id}/products",
        json=product_payload(
            default_product_type_code,
            default_material_item_id,
            **overrides,
        ),
    )


async def add_production_order(
    db_session: AsyncSession,
    product: dict[str, object],
) -> None:
    order_type = OrderType(
        code="TEST_ORDER_TYPE",
        name_ru="Тестовый тип заказа",
        ics_section="03.100.50",
        ref_system="Test",
        ref_code="TEST_ORDER_TYPE",
        description="Test fixture for Product lifecycle API.",
    )
    industry = Industry(
        code="TEST_INDUSTRY",
        name_ru="Тестовая отрасль",
        ics_section="25.000.00",
        ref_system="Test",
        ref_code="TEST_INDUSTRY",
        description="Test fixture for Product lifecycle API.",
    )
    order = ProductionOrder(
        profile_id=product["profile_id"],
        order_type_code=order_type.code,
        product_id=product["id"],
        industry_code=industry.code,
        order_number="ORDER-API-1",
        quantity=1,
        deadline=date(2027, 1, 1),
    )
    db_session.add_all([order_type, industry, order])
    await db_session.commit()


async def test_product_api_profile_scoped_crud_and_patch_semantics(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    profile_id = api_profile["id"]

    empty_list = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/products"
    )
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    create_response = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="  Case-SKU  ",
        name="  Тестовое изделие  ",
    )
    assert create_response.status_code == 200
    created = create_response.json()
    product_id = created["id"]
    assert created == {
        "id": product_id,
        "profile_id": profile_id,
        "product_type_code": product_type_code,
        "material_item_id": material_item["id"],
        "sku_code": "Case-SKU",
        "name": "Тестовое изделие",
        "weight_net": 12.5,
        "required_it_grade": 8,
        "required_ra": 1.6,
    }

    list_response = await api_client.get(
        f"/api/v1/enterprises/{profile_id}/products"
    )
    get_response = await api_client.get(f"/api/v1/products/{product_id}")
    assert list_response.status_code == 200
    assert list_response.json() == [created]
    assert get_response.status_code == 200
    assert get_response.json() == created

    clear_response = await api_client.patch(
        f"/api/v1/products/{product_id}",
        json={
            "name": "  Обновлённое изделие  ",
            "required_it_grade": None,
            "required_ra": None,
        },
    )
    assert clear_response.status_code == 200
    cleared = clear_response.json()
    assert cleared["name"] == "Обновлённое изделие"
    assert cleared["required_it_grade"] is None
    assert cleared["required_ra"] is None
    assert cleared["sku_code"] == "Case-SKU"
    assert cleared["weight_net"] == 12.5

    empty_patch = await api_client.patch(
        f"/api/v1/products/{product_id}",
        json={},
    )
    assert empty_patch.status_code == 200
    assert empty_patch.json() == cleared

    delete_response = await api_client.delete(f"/api/v1/products/{product_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == product_id
    assert (await api_client.get(f"/api/v1/products/{product_id}")).status_code == 404


async def test_profile_scoped_routes_reject_missing_profile_first(
    api_client: AsyncClient,
) -> None:
    list_response = await api_client.get(
        "/api/v1/enterprises/999999/products"
    )
    create_response = await create_product(
        api_client,
        999999,
        "FINISHED_GOOD",
        999999,
    )

    assert list_response.status_code == 404
    assert list_response.json() == {
        "detail": "Enterprise profile 999999 not found."
    }
    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Enterprise profile 999999 not found."
    }


async def test_create_rejects_unknown_product_type(
    api_client: AsyncClient,
    api_profile: dict[str, object],
) -> None:
    response = await create_product(
        api_client,
        api_profile["id"],
        "NO_SUCH_TYPE",
        999999,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product type NO_SUCH_TYPE not found."}


async def test_create_rejects_unknown_material_item(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
) -> None:
    product_type_code = await add_product_type(db_session)

    response = await create_product(
        api_client,
        api_profile["id"],
        product_type_code,
        999999,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Material item 999999 not found."}


async def test_duplicate_is_trimmed_exact_and_case_sensitive(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    profile_id = api_profile["id"]
    first = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="Case-SKU",
    )
    duplicate = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="  Case-SKU  ",
    )
    case_variant = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="case-sku",
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"Product {profile_id}/Case-SKU already exists."
    }
    assert case_variant.status_code == 200
    assert case_variant.json()["sku_code"] == "case-sku"


@pytest.mark.parametrize(
    ("field_name", "value", "expected_detail"),
    [
        (
            "product_type_code",
            "NO_SUCH_TYPE",
            "Product type NO_SUCH_TYPE not found.",
        ),
        (
            "material_item_id",
            999999,
            "Material item 999999 not found.",
        ),
    ],
)
async def test_patch_rejects_unknown_replacement_reference(
    field_name: str,
    value: object,
    expected_detail: str,
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    created = await create_product(
        api_client,
        api_profile["id"],
        product_type_code,
        material_item["id"],
    )
    assert created.status_code == 200

    response = await api_client.patch(
        f"/api/v1/products/{created.json()['id']}",
        json={field_name: value},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": expected_detail}


async def test_patch_rejects_duplicate_resulting_sku(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    profile_id = api_profile["id"]
    first = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="First-SKU",
    )
    second = await create_product(
        api_client,
        profile_id,
        product_type_code,
        material_item["id"],
        sku_code="Second-SKU",
    )
    assert first.status_code == 200
    assert second.status_code == 200

    duplicate = await api_client.patch(
        f"/api/v1/products/{second.json()['id']}",
        json={"sku_code": "  First-SKU  "},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"Product {profile_id}/First-SKU already exists."
    }


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("post", {"sku_code": "   "}),
        ("post", {"name": "   "}),
        ("post", {"weight_net": 0}),
        ("post", {"weight_net": -1}),
        ("post", {"required_it_grade": 0}),
        ("post", {"required_it_grade": 19}),
        ("post", {"required_ra": 0}),
        ("post", {"product_type_code": None}),
        ("post", {"material_item_id": None}),
        ("post", {"sku_code": None}),
        ("post", {"name": None}),
        ("post", {"weight_net": None}),
        ("patch", {"sku_code": "   "}),
        ("patch", {"name": "   "}),
        ("patch", {"weight_net": 0}),
        ("patch", {"required_it_grade": 19}),
        ("patch", {"required_ra": -1}),
        ("patch", {"product_type_code": None}),
        ("patch", {"material_item_id": None}),
        ("patch", {"sku_code": None}),
        ("patch", {"name": None}),
        ("patch", {"weight_net": None}),
    ],
)
async def test_api_exposes_business_payload_validation_as_422(
    method: str,
    payload: dict[str, object],
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    if method == "post":
        response = await create_product(
            api_client,
            api_profile["id"],
            product_type_code,
            material_item["id"],
            **payload,
        )
    else:
        created = await create_product(
            api_client,
            api_profile["id"],
            product_type_code,
            material_item["id"],
        )
        assert created.status_code == 200
        response = await api_client.patch(
            f"/api/v1/products/{created.json()['id']}",
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


async def test_missing_product_item_routes_return_domain_404(
    api_client: AsyncClient,
) -> None:
    get_response = await api_client.get("/api/v1/products/999999")
    patch_response = await api_client.patch(
        "/api/v1/products/999999",
        json={},
    )
    delete_response = await api_client.delete("/api/v1/products/999999")

    assert get_response.status_code == 404
    assert get_response.json() == {"detail": "Product 999999 not found."}
    assert patch_response.status_code == 404
    assert patch_response.json() == {"detail": "Product 999999 not found."}
    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "Product 999999 not found."}


async def test_used_product_is_immutable_but_empty_patch_remains_no_op(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    product_type_code = await add_product_type(db_session)
    material_item = await create_material_item(api_client, reference_rows)
    created_response = await create_product(
        api_client,
        api_profile["id"],
        product_type_code,
        material_item["id"],
    )
    assert created_response.status_code == 200
    created = created_response.json()
    product_id = created["id"]
    await add_production_order(db_session, created)

    changed = await api_client.patch(
        f"/api/v1/products/{product_id}",
        json={"name": created["name"]},
    )
    empty = await api_client.patch(
        f"/api/v1/products/{product_id}",
        json={},
    )
    deleted = await api_client.delete(f"/api/v1/products/{product_id}")
    persisted = await api_client.get(f"/api/v1/products/{product_id}")

    assert changed.status_code == 409
    assert changed.json() == {
        "detail": (
            f"Product {product_id} is used by production orders "
            "and cannot be changed."
        )
    }
    assert empty.status_code == 200
    assert empty.json() == created
    assert deleted.status_code == 409
    assert deleted.json() == {
        "detail": f"Product {product_id} is used by production orders."
    }
    assert persisted.status_code == 200
    assert persisted.json() == created
