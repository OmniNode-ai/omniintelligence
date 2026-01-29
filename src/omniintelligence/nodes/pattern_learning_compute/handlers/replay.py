"""Replay artifact emission for pattern learning handlers.

This module provides a protocol for emitting structured replay artifacts
during pattern learning operations. Artifacts enable replay comparison
and debugging of clustering decisions.

Design:
    - Protocol-based for dependency injection
    - NullEmitter for tests and when replay logging is disabled
    - JSON-safe payload enforcement
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable


def assert_json_safe(payload: object) -> None:
    """Validate that payload is JSON-serializable.

    Args:
        payload: Object to validate.

    Raises:
        TypeError: If payload cannot be serialized to JSON.
    """
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise TypeError(f"Replay artifact payload is not JSON-safe: {e}") from e


@runtime_checkable
class ReplayArtifactEmitter(Protocol):
    """Protocol for emitting replay artifacts during computation.

    Implementations can log to files, send to observability systems,
    or no-op for tests.
    """

    def emit(self, name: str, payload: dict[str, object]) -> None:
        """Emit a replay artifact.

        Args:
            name: Artifact name (e.g., "cluster_assignment_map", "clustering_result").
            payload: JSON-serializable dict containing the artifact data.
        """
        ...


class NullEmitter:
    """No-op emitter for tests and when replay logging is disabled.

    Note:
        Still validates JSON-safety to catch serialization bugs early in tests.
        Even though data is discarded, validation ensures that production
        emitters would also succeed.
    """

    def emit(self, name: str, payload: dict[str, object]) -> None:
        """Validate payload is JSON-safe, then discard.

        Args:
            name: Artifact name (unused but validated for protocol compliance).
            payload: JSON-serializable dict - validated then discarded.

        Raises:
            TypeError: If payload is not JSON-serializable.
        """
        assert_json_safe(payload)  # Catch serialization bugs early in tests


# Default instance for convenience
NULL_EMITTER = NullEmitter()


__all__ = [
    "NULL_EMITTER",
    "NullEmitter",
    "ReplayArtifactEmitter",
    "assert_json_safe",
]
