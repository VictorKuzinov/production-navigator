from typing import Any, Literal

from app.schemas import ErrorResponse

type ErrorStatus = Literal[404, 409]
type OpenAPIResponses = dict[int | str, dict[str, Any]]

_ERROR_RESPONSE_DEFINITIONS: dict[ErrorStatus, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": "Requested resource or referenced resource was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": (
            "Request conflicts with the current state of the target resource."
        ),
    },
}


def error_responses(*status_codes: ErrorStatus) -> OpenAPIResponses:
    """Return fresh OpenAPI metadata for reachable custom error responses."""
    responses: OpenAPIResponses = {}

    for status_code in status_codes:
        responses[status_code] = _ERROR_RESPONSE_DEFINITIONS[status_code].copy()

    return responses
