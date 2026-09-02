from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import CapabilityState, ProfileSectionCode, ProfileSectionState
from app.schemas.profile_capabilities import (
    CapabilityStateUpdate,
    ProfileSectionCompletenessRead,
    ProfileSectionConfirmation,
    ProfileSectionStateUpdate,
)


def test_foundation_enums_have_exact_approved_values() -> None:
    assert [state.value for state in CapabilityState] == [
        "SUPPORTED",
        "UNSUPPORTED",
        "UNKNOWN",
    ]
    assert [code.value for code in ProfileSectionCode] == [
        "TECHNOLOGIES",
        "MATERIALS",
    ]
    assert [state.value for state in ProfileSectionState] == [
        "CONFIRMED_COMPLETE",
        "PARTIAL",
        "UNKNOWN",
    ]


@pytest.mark.parametrize("state", list(CapabilityState))
def test_capability_state_update_accepts_each_explicit_state(
    state: CapabilityState,
) -> None:
    assert CapabilityStateUpdate.model_validate({"state": state}).state == state


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"state": "NO_ASSERTION"},
        {"state": "SUPPORTED", "expected_revision": 1},
    ],
)
def test_capability_state_update_rejects_omission_invalid_and_revision_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CapabilityStateUpdate.model_validate(payload)


@pytest.mark.parametrize("state", ["PARTIAL", "UNKNOWN"])
def test_section_state_update_accepts_only_mutable_states(state: str) -> None:
    assert ProfileSectionStateUpdate.model_validate({"state": state}).state == state


@pytest.mark.parametrize(
    "payload",
    [
        {"state": "CONFIRMED_COMPLETE"},
        {"state": "PARTIAL", "content_revision": 1},
    ],
)
def test_section_state_update_rejects_complete_and_revision_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ProfileSectionStateUpdate.model_validate(payload)


def test_confirmation_trims_and_bounds_confirmer() -> None:
    assert (
        ProfileSectionConfirmation.model_validate(
            {"confirmed_by": "  operator-1  "}
        ).confirmed_by
        == "operator-1"
    )

    for invalid in ["   ", "x" * 129]:
        with pytest.raises(ValidationError):
            ProfileSectionConfirmation.model_validate(
                {"confirmed_by": invalid}
            )


@pytest.mark.parametrize("extra_field", ["confirmed_at", "expected_revision"])
def test_confirmation_rejects_client_timestamp_and_revision(
    extra_field: str,
) -> None:
    with pytest.raises(ValidationError):
        ProfileSectionConfirmation.model_validate(
            {
                "confirmed_by": "operator",
                extra_field: "2026-09-02T00:00:00Z",
            }
        )


def test_section_response_contains_only_current_state_and_confirmation_metadata(
) -> None:
    response = ProfileSectionCompletenessRead.model_validate(
        {
            "profile_id": 7,
            "section_code": "TECHNOLOGIES",
            "state": "CONFIRMED_COMPLETE",
            "confirmed_at": datetime(2026, 9, 2, tzinfo=UTC),
            "confirmed_by": "operator",
        }
    )

    assert set(response.model_dump()) == {
        "profile_id",
        "section_code",
        "state",
        "confirmed_at",
        "confirmed_by",
    }
