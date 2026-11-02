# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Enums of the agent receipt verifier (OMN-22175)."""

from __future__ import annotations

from enum import StrEnum


class EnumAgentReceiptDecision(StrEnum):
    """The verifier's answer."""

    ACCEPTED = "accepted"
    REFUSED = "refused"


class EnumAgentReceiptRefusal(StrEnum):
    """Why a receipt was refused; one reason per rule, never shared."""

    MISSING_SIGNATURE = "missing_signature"
    FORGED_SIGNATURE = "forged_signature"
    REPOSITORY_DIFFERS = "repository_differs"
    PULL_REQUEST_DIFFERS = "pull_request_differs"
    HEAD_DIFFERS = "head_differs"
    BLOCKED_VERDICT = "blocked_verdict"
    MISSING_PROVENANCE = "missing_provenance"
    FORBIDDEN_PROVIDER = "forbidden_provider"
    FORBIDDEN_ENDPOINT_CLASS = "forbidden_endpoint_class"
    FORBIDDEN_ENDPOINT = "forbidden_endpoint"
    UNKNOWN_VOTER = "unknown_voter"
    DUPLICATE_IDENTITY = "duplicate_identity"
    BELOW_QUORUM = "below_quorum"


class EnumAgentReceiptVerifyTransport(StrEnum):
    """The bus binding the node's overlay selects."""

    IN_MEMORY = "in_memory"
    REDPANDA = "redpanda"


__all__ = [
    "EnumAgentReceiptDecision",
    "EnumAgentReceiptRefusal",
    "EnumAgentReceiptVerifyTransport",
]
