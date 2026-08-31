from typing import Any

from app.main import app

type OperationKey = tuple[str, str]
type OpenAPISchema = dict[str, Any]

HTTP_METHODS = {"get", "post", "patch", "delete"}
CUSTOM_ERROR_STATUSES = {"404", "409"}
ERROR_RESPONSE_REF = {"$ref": "#/components/schemas/ErrorResponse"}

EXPECTED_CUSTOM_ERROR_RESPONSES: dict[OperationKey, set[str]] = {
    ("get", "/api/v1/enterprises/{profile_id}"): {"404"},
    ("patch", "/api/v1/enterprises/{profile_id}"): {"404"},
    ("delete", "/api/v1/enterprises/{profile_id}"): {"404"},
    ("get", "/api/v1/enterprises/{profile_id}/facilities"): {"404"},
    ("post", "/api/v1/enterprises/{profile_id}/facilities"): {"404"},
    ("get", "/api/v1/facilities/{facility_id}"): {"404"},
    ("patch", "/api/v1/facilities/{facility_id}"): {"404"},
    ("delete", "/api/v1/facilities/{facility_id}"): {"404"},
    (
        "get",
        "/api/v1/enterprises/{profile_id}/facilities/{facility_id}/equipment",
    ): {"404"},
    (
        "post",
        "/api/v1/enterprises/{profile_id}/facilities/{facility_id}/equipment",
    ): {"404"},
    ("get", "/api/v1/equipment/{equipment_id}"): {"404"},
    ("patch", "/api/v1/equipment/{equipment_id}"): {"404"},
    ("delete", "/api/v1/equipment/{equipment_id}"): {"404"},
    ("get", "/api/v1/enterprises/{profile_id}/warehouses"): {"404"},
    ("post", "/api/v1/enterprises/{profile_id}/warehouses"): {"404"},
    ("get", "/api/v1/warehouses/{warehouse_id}"): {"404"},
    ("patch", "/api/v1/warehouses/{warehouse_id}"): {"404"},
    ("delete", "/api/v1/warehouses/{warehouse_id}"): {"404"},
    (
        "get",
        "/api/v1/enterprises/{profile_id}/lifting-equipment",
    ): {"404"},
    (
        "post",
        "/api/v1/enterprises/{profile_id}/lifting-equipment",
    ): {"404"},
    (
        "get",
        "/api/v1/lifting-equipment/{lifting_equipment_id}",
    ): {"404"},
    (
        "patch",
        "/api/v1/lifting-equipment/{lifting_equipment_id}",
    ): {"404"},
    (
        "delete",
        "/api/v1/lifting-equipment/{lifting_equipment_id}",
    ): {"404"},
    ("get", "/api/v1/enterprises/{profile_id}/transports"): {"404"},
    ("post", "/api/v1/enterprises/{profile_id}/transports"): {"404"},
    ("get", "/api/v1/transports/{transport_id}"): {"404"},
    ("patch", "/api/v1/transports/{transport_id}"): {"404"},
    ("delete", "/api/v1/transports/{transport_id}"): {"404"},
    ("post", "/api/v1/materials"): {"404", "409"},
    ("get", "/api/v1/materials/{material_id}"): {"404"},
    ("patch", "/api/v1/materials/{material_id}"): {"404", "409"},
    ("delete", "/api/v1/materials/{material_id}"): {"404", "409"},
    ("post", "/api/v1/material-items"): {"404", "409"},
    ("get", "/api/v1/material-items/{material_item_id}"): {"404"},
    (
        "patch",
        "/api/v1/material-items/{material_item_id}",
    ): {"404", "409"},
    (
        "delete",
        "/api/v1/material-items/{material_item_id}",
    ): {"404", "409"},
    ("get", "/api/v1/enterprises/{profile_id}/products"): {"404"},
    (
        "post",
        "/api/v1/enterprises/{profile_id}/products",
    ): {"404", "409"},
    ("get", "/api/v1/products/{product_id}"): {"404"},
    ("patch", "/api/v1/products/{product_id}"): {"404", "409"},
    ("delete", "/api/v1/products/{product_id}"): {"404", "409"},
}


def _fresh_openapi() -> OpenAPISchema:
    previous_schema = app.openapi_schema
    app.openapi_schema = None
    try:
        return app.openapi()
    finally:
        app.openapi_schema = previous_schema


def _custom_error_manifest(
    schema: OpenAPISchema,
) -> dict[OperationKey, set[str]]:
    manifest: dict[OperationKey, set[str]] = {}

    for path, path_item in schema["paths"].items():
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue

            custom_statuses = set(operation["responses"]) & CUSTOM_ERROR_STATUSES
            if custom_statuses:
                manifest[(method, path)] = custom_statuses

    return manifest


def test_openapi_declares_exact_reachable_custom_error_statuses() -> None:
    schema = _fresh_openapi()

    assert _custom_error_manifest(schema) == EXPECTED_CUSTOM_ERROR_RESPONSES


def test_openapi_custom_errors_use_shared_detail_schema() -> None:
    schema = _fresh_openapi()

    for (method, path), statuses in EXPECTED_CUSTOM_ERROR_RESPONSES.items():
        responses = schema["paths"][path][method]["responses"]
        for status_code in statuses:
            response_schema = responses[status_code]["content"]["application/json"][
                "schema"
            ]
            assert response_schema == ERROR_RESPONSE_REF

    error_response = schema["components"]["schemas"]["ErrorResponse"]
    assert set(error_response["properties"]) == {"detail"}
    assert error_response["properties"]["detail"]["type"] == "string"
    assert error_response["required"] == ["detail"]


def test_openapi_custom_error_metadata_preserves_existing_responses() -> None:
    first_schema = _fresh_openapi()
    second_schema = _fresh_openapi()

    assert _custom_error_manifest(first_schema) == _custom_error_manifest(second_schema)

    for method, path in EXPECTED_CUSTOM_ERROR_RESPONSES:
        response_statuses = set(first_schema["paths"][path][method]["responses"])
        assert {"200", "422"} <= response_statuses
