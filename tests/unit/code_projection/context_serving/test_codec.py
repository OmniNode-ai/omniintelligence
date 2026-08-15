# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical request and authorization contract proofs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omniintelligence.code_projection.context_serving.codec import (
    parse_authorization_profile,
    parse_code_context_request,
    serialize_authorization_profile,
    serialize_code_context_request,
)
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextRequestError,
)
from omniintelligence.code_projection.context_serving.models import (
    derive_projection_repository_id,
)
from tests.unit.code_projection.context_serving.fixtures import (
    QUERY_TEXT,
    REPOSITORY_ID,
    REPOSITORY_INSTANCE_ID,
    build_scenario,
)

pytestmark = pytest.mark.unit


def test_request_and_profile_round_trip_as_exact_canonical_bytes(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path)

    assert parse_code_context_request(scenario.request_bytes) == scenario.request
    assert serialize_code_context_request(scenario.request) == scenario.request_bytes
    profile_bytes = serialize_authorization_profile(scenario.profile)
    assert parse_authorization_profile(profile_bytes) == scenario.profile


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: b"{\n  " + payload[1:],
        lambda payload: payload.replace(
            b'"request_id":', b'"request_id":"duplicate","request_id":', 1
        ),
        lambda payload: payload.replace(QUERY_TEXT.encode("utf-8"), b" ", 1),
    ],
)
def test_request_rejects_noncanonical_duplicate_or_invalid_payload(
    tmp_path: Path,
    mutate: object,
) -> None:
    scenario = build_scenario(tmp_path)
    mutation = mutate
    assert callable(mutation)

    with pytest.raises(CodeContextRequestError) as raised:
        parse_code_context_request(mutation(scenario.request_bytes))

    assert QUERY_TEXT not in str(raised.value)


def test_request_rejects_extra_fields_without_echoing_query(tmp_path: Path) -> None:
    scenario = build_scenario(tmp_path)
    decoded = json.loads(scenario.request_bytes)
    decoded["untrusted_scope"] = QUERY_TEXT
    payload = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()

    with pytest.raises(CodeContextRequestError) as raised:
        parse_code_context_request(payload)

    assert QUERY_TEXT not in str(raised.value)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("repository_instance_id", "worktree/OMN-16068"),
        ("projection_repository_id", REPOSITORY_ID),
        ("policy_scope_ref", "tenant:wrong:repository:scope"),
    ],
)
def test_request_rejects_untrusted_or_mismatched_repository_coordinates(
    tmp_path: Path,
    field_name: str,
    value: str,
) -> None:
    scenario = build_scenario(tmp_path)
    decoded = json.loads(scenario.request_bytes)
    decoded[field_name] = value
    payload = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()

    with pytest.raises(CodeContextRequestError):
        parse_code_context_request(payload)


def test_projection_repository_identity_is_checkout_instance_scoped() -> None:
    assert (
        derive_projection_repository_id(
            repository_id=REPOSITORY_ID,
            repository_instance_id="canonical",
        )
        == REPOSITORY_ID
    )
    assert (
        derive_projection_repository_id(
            repository_id=REPOSITORY_ID,
            repository_instance_id=REPOSITORY_INSTANCE_ID,
        )
        == f"{REPOSITORY_ID}/instances/{REPOSITORY_INSTANCE_ID}"
    )
    remote_instance = "remote/devbox-a"
    assert (
        derive_projection_repository_id(
            repository_id=REPOSITORY_ID,
            repository_instance_id=remote_instance,
        )
        == f"{REPOSITORY_ID}/instances/{remote_instance}"
    )


def test_authorization_rejects_a_scope_not_bound_to_its_instance(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path)
    decoded = json.loads(serialize_authorization_profile(scenario.profile))
    scope = decoded["grants"][0]["repository_scopes"][0]
    scope["repository_instance_id"] = "canonical"
    payload = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()

    with pytest.raises(CodeContextRequestError):
        parse_authorization_profile(payload)


def test_projection_identity_reserves_delimiter_against_noninjective_collision() -> (
    None
):
    assert (
        derive_projection_repository_id(
            repository_id="foo",
            repository_instance_id="bar",
        )
        == "foo/instances/bar"
    )
    with pytest.raises(ValueError, match="reserved instances namespace"):
        derive_projection_repository_id(
            repository_id="foo/instances/bar",
            repository_instance_id="canonical",
        )


def test_repository_instance_cannot_enter_projection_instance_namespace() -> None:
    with pytest.raises(ValueError, match="reserved instances namespace"):
        derive_projection_repository_id(
            repository_id="foo",
            repository_instance_id="remote/instances/bar",
        )
