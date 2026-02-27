# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""EvidenceBundle and EvidenceItem models (OMN-2537).

An EvidenceBundle is a fingerprinted, immutable collection of evidence items
gathered during an agent execution run. The bundle fingerprint is a SHA-256
hash computed deterministically over the serialized items — NOT a timestamp.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Known typed evidence sources — free-text is rejected
KNOWN_EVIDENCE_SOURCES: frozenset[str] = frozenset(
    {
        "lint_result",
        "test_result",
        "coverage_report",
        "mypy_report",
        "latency_measurement",
        "cost_measurement",
        "human_rating",
        "safety_check",
        "code_review",
        "benchmark_result",
    }
)


class ModelEvidenceItem(BaseModel):
    """A single piece of evidence from an agent execution run.

    Evidence items carry typed, structured data. Free-text `source` values
    are rejected — only known source types are permitted.
    """

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(
        description="Unique identifier for this evidence item within the bundle."
    )
    source: str = Field(
        description=(
            "Typed source of the evidence. Must be one of the known source types. "
            "Free-text values are rejected."
        )
    )
    value: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized evidence value in [0.0, 1.0].",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured metadata about this evidence item.",
    )

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Reject free-text sources — only known typed sources allowed."""
        if v not in KNOWN_EVIDENCE_SOURCES:
            raise ValueError(
                f"Unknown evidence source '{v}'. "
                f"Must be one of: {sorted(KNOWN_EVIDENCE_SOURCES)}"
            )
        return v


class ModelEvidenceBundle(BaseModel):
    """Immutable, fingerprinted collection of evidence items for a run.

    The bundle_fingerprint is the canonical SHA-256 hash of the serialized
    items list. It is deterministic: same items → same fingerprint.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(
        description="Identifier of the agent execution run this bundle belongs to."
    )
    bundle_fingerprint: str = Field(
        description=(
            "SHA-256 hex digest of the deterministically serialized items. "
            "Computed via ModelEvidenceBundle.fingerprint(items)."
        )
    )
    items: tuple[ModelEvidenceItem, ...] = Field(
        description="Ordered, immutable sequence of evidence items.",
    )
    collected_at_utc: str = Field(
        description="ISO-8601 UTC timestamp when evidence was collected.",
    )

    @classmethod
    def fingerprint(cls, items: tuple[ModelEvidenceItem, ...]) -> str:
        """Compute SHA-256 fingerprint over deterministically serialized items.

        The fingerprint is content-addressed: same items in same order →
        same fingerprint. Items are serialized to JSON with sorted keys.

        Args:
            items: Ordered tuple of evidence items.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        serialized = json.dumps(
            [
                {
                    "item_id": item.item_id,
                    "source": item.source,
                    "value": item.value,
                    "metadata": item.metadata,
                }
                for item in items
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = ["ModelEvidenceBundle", "ModelEvidenceItem"]
