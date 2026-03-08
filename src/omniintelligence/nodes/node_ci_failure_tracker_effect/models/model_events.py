# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""V1 event payload schemas for Debug Intelligence topics.

These are the canonical payload shapes for cross-repo integration.
Do NOT change field names or types without incrementing the topic version.

Topic: onex.cmd.omniintelligence.ci-failure-detected.v1
Topic: onex.cmd.omniintelligence.ci-recovery-detected.v1
Topic: onex.evt.omniintelligence.debug-trigger-record-created.v1
Topic: onex.evt.omniintelligence.debug-fix-record-created.v1

Ticket: OMN-3556
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelCiFailureDetectedV1(BaseModel):
    """Payload for ci-failure-detected.v1.

    Produced by CI webhook handler when a GitHub Actions run fails.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_id: str  # Unique event ID for idempotency
    repo: str  # e.g. "OmniNode-ai/omniintelligence"
    branch: str  # e.g. "main" or "jonah/omn-1234"
    sha: str  # Git SHA of failing run
    pr_number: int | None = None  # PR number if applicable
    run_id: str  # GitHub Actions run ID
    job_name: str  # Failing job name
    # Raw failure output — fingerprinter and classifier operate on this
    failure_output: str
    # changed_files: list of files changed in this SHA (for retrieval precision)
    changed_files: list[str] = Field(default_factory=list)
    emitted_at: str  # ISO 8601, injected by caller


class ModelCiRecoveryDetectedV1(BaseModel):
    """Payload for ci-recovery-detected.v1.

    Produced when a GitHub Actions run succeeds after prior failures.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_id: str
    repo: str
    branch: str
    sha: str
    pr_number: int | None = None
    run_id: str
    # changed_files: used for regression_test_added heuristic
    changed_files: list[str] = Field(default_factory=list)
    emitted_at: str


class ModelDebugTriggerRecordCreatedV1(BaseModel):
    """Payload for debug-trigger-record-created.v1.

    Emitted when a TriggerRecord is created (streak threshold crossed).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    trigger_record_id: UUID
    repo: str
    branch: str
    failure_fingerprint: str
    error_classification: str
    # observed_bad_sha: the SHA present when threshold was crossed.
    # NOT necessarily the first bad commit (Phase 2 will add bisect result).
    observed_bad_sha: str
    streak_count_at_trigger: int
    emitted_at: str


class ModelDebugFixRecordCreatedV1(BaseModel):
    """Payload for debug-fix-record-created.v1.

    Emitted when a FixRecord is created and its TriggerRecord is resolved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    fix_record_id: UUID
    trigger_record_id: UUID
    repo: str
    sha: str
    pr_number: int | None = None
    regression_test_added: bool
    emitted_at: str


__all__ = [
    "ModelCiFailureDetectedV1",
    "ModelCiRecoveryDetectedV1",
    "ModelDebugFixRecordCreatedV1",
    "ModelDebugTriggerRecordCreatedV1",
]
