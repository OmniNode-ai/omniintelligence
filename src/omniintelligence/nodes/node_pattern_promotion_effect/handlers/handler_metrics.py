# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Prometheus-style observability metrics for the pattern promotion effect node.

This module defines and exposes Prometheus counters and gauges that are emitted
during pattern promotion check operations. All metrics use the
``pattern_promotion_`` prefix for discoverability.

Metric Registry (OMN-1739)
--------------------------
The following metrics are emitted by ``record_promotion_check_metrics()``
after each ``check_and_promote_patterns()`` call:

Counter (monotonically increasing):
    ``promotion_check_patterns_total``
        Total provisional patterns inspected in this node's lifetime.
        Labels: none.

    ``promotion_check_patterns_eligible_total``
        Total patterns that passed all promotion gates (eligible for promotion),
        regardless of whether Kafka emit succeeded.
        Labels: none.

    ``promotion_check_patterns_promoted_total``
        Total patterns for which a lifecycle event was successfully emitted
        to Kafka (``promoted_at`` is set, not dry_run).
        Labels: none.

    ``promotion_check_patterns_failed_total``
        Total patterns for which promotion was attempted but the Kafka emit
        failed (``promoted_at`` is None, not dry_run, not skipped for Kafka
        unavailability — only emission failures counted here).
        Labels: none.

    ``promotion_check_patterns_skipped_total``
        Total patterns skipped because the Kafka producer was unavailable
        (``promotion_skipped: kafka_producer_unavailable`` reason).
        Labels: none.

    ``promotion_check_dry_run_total``
        Total dry-run promotion checks performed (dry_run=True invocations).
        Labels: none.

Gauge (last-write-wins, useful for dashboards):
    ``promotion_check_last_patterns_checked``
        Number of patterns inspected in the most recent non-dry-run check.

    ``promotion_check_last_patterns_eligible``
        Number of eligible patterns in the most recent non-dry-run check.

    ``promotion_check_last_patterns_promoted``
        Number of successfully promoted patterns in the most recent
        non-dry-run check.

Design Notes
------------
- Metrics objects are module-level singletons registered with the default
  ``prometheus_client.REGISTRY``.  This is the standard prometheus_client
  pattern — one registration per process lifetime.
- ``record_promotion_check_metrics()`` is a pure side-effect function with
  no return value. It is safe to call from async handlers because
  prometheus_client counter/gauge operations are thread-safe and do not
  block.
- The ``_METRICS_ENABLED`` flag (default True) can be set to False in test
  environments to suppress registration errors when multiple test processes
  share a registry. Tests should prefer importing
  ``record_promotion_check_metrics`` and calling it directly.
- All metric names follow the Prometheus naming convention:
  ``<namespace>_<subsystem>_<name>_<unit_suffix>``.

Reference
---------
    OMN-1739: Add observability metrics to pattern promotion effect node
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckResult,
    )

logger = logging.getLogger(__name__)

# =============================================================================
# Metric Definitions
# =============================================================================
# Metrics are registered lazily to avoid import-time side effects in test
# environments where multiple instances might share the default registry.

_METRICS_INITIALIZED = False
_COUNTERS: dict[str, object] = {}
_GAUGES: dict[str, object] = {}


def _init_metrics() -> None:
    """Initialize and register Prometheus metric objects (idempotent).

    Called once on first use.  Protected against double-registration by
    ``_METRICS_INITIALIZED`` guard and prometheus_client's own registry
    deduplication.
    """
    global _METRICS_INITIALIZED  # noqa: PLW0603 - intentional module-level singleton

    if _METRICS_INITIALIZED:
        return

    try:
        from prometheus_client import Counter, Gauge  # type: ignore[import-untyped]

        _COUNTERS["patterns_total"] = Counter(
            "promotion_check_patterns_total",
            "Total provisional patterns inspected across all promotion check calls.",
        )
        _COUNTERS["eligible_total"] = Counter(
            "promotion_check_patterns_eligible_total",
            "Total patterns that passed all promotion gates.",
        )
        _COUNTERS["promoted_total"] = Counter(
            "promotion_check_patterns_promoted_total",
            "Total patterns for which a Kafka lifecycle event was successfully emitted.",
        )
        _COUNTERS["failed_total"] = Counter(
            "promotion_check_patterns_failed_total",
            "Total patterns where promotion was attempted but Kafka emit failed.",
        )
        _COUNTERS["skipped_total"] = Counter(
            "promotion_check_patterns_skipped_total",
            "Total patterns skipped because the Kafka producer was unavailable.",
        )
        _COUNTERS["dry_run_total"] = Counter(
            "promotion_check_dry_run_total",
            "Total dry-run promotion check calls (dry_run=True).",
        )

        _GAUGES["last_checked"] = Gauge(
            "promotion_check_last_patterns_checked",
            "Number of patterns inspected in the most recent non-dry-run check.",
        )
        _GAUGES["last_eligible"] = Gauge(
            "promotion_check_last_patterns_eligible",
            "Number of eligible patterns in the most recent non-dry-run check.",
        )
        _GAUGES["last_promoted"] = Gauge(
            "promotion_check_last_patterns_promoted",
            "Number of successfully promoted patterns in the most recent non-dry-run check.",
        )

        _METRICS_INITIALIZED = True
        logger.debug("Promotion check Prometheus metrics initialized.")

    except ValueError as exc:
        # prometheus_client raises ValueError on duplicate registration (e.g. in
        # parallel test runs sharing the same process-level registry). Log and
        # proceed — metrics are best-effort and must not break the main flow.
        logger.warning(
            "Failed to register promotion check metrics (possible duplicate "
            "registration in test environment): %s",
            exc,
        )
        _METRICS_INITIALIZED = True  # Prevent infinite retry

    except Exception as exc:  # broad-catch-ok: prometheus_client registration boundary
        logger.warning(
            "Unexpected error initializing promotion check metrics: %s",
            exc,
            exc_info=True,
        )
        _METRICS_INITIALIZED = True  # Prevent infinite retry


# =============================================================================
# Public API
# =============================================================================


def record_promotion_check_metrics(result: ModelPromotionCheckResult) -> None:
    """Emit Prometheus metrics for a completed promotion check.

    This is a fire-and-forget function — it records metrics from
    ``result`` into the module-level counters and gauges.  Failures
    are logged at WARNING level and never propagate to the caller.

    This function is called by ``check_and_promote_patterns()`` after the
    promotion check completes, regardless of whether individual promotions
    succeeded or failed.

    Args:
        result: The completed ModelPromotionCheckResult to record metrics for.

    Metrics updated:
        - ``promotion_check_patterns_total``    += result.patterns_checked
        - ``promotion_check_patterns_eligible_total`` += result.patterns_eligible
        - ``promotion_check_patterns_promoted_total`` += result.patterns_succeeded
        - ``promotion_check_patterns_failed_total``   += result.patterns_failed
        - ``promotion_check_patterns_skipped_total``  += <skipped count>
        - ``promotion_check_dry_run_total``      += 1 if dry_run else 0
        - ``promotion_check_last_*`` gauges      set if not dry_run

    Note:
        Skipped patterns are those with ``reason`` containing
        ``kafka_producer_unavailable`` and ``promoted_at is None``
        and ``not dry_run``. These are distinct from failures because
        skipping is an expected degraded-mode behavior, not an error.
    """
    _init_metrics()

    try:
        _record(result)
    except Exception as exc:  # broad-catch-ok: metrics are best-effort
        logger.warning(
            "Failed to record promotion check metrics: %s",
            exc,
            exc_info=True,
        )


def _record(result: ModelPromotionCheckResult) -> None:
    """Inner implementation — may raise; caller catches and logs."""
    # Count skipped-due-to-Kafka patterns: promoted_at is None, not dry_run,
    # and the reason indicates Kafka unavailability (not a hard failure).
    skipped_count = sum(
        1
        for r in result.patterns_promoted
        if (
            r.promoted_at is None
            and not r.dry_run
            and "kafka_producer_unavailable" in (r.reason or "")
        )
    )

    # Increment counters — these are safe to call even if _COUNTERS is partially
    # populated (e.g., if initialization raised on some metrics).

    if "patterns_total" in _COUNTERS:
        _COUNTERS["patterns_total"].inc(result.patterns_checked)  # type: ignore[union-attr]

    if "eligible_total" in _COUNTERS:
        _COUNTERS["eligible_total"].inc(result.patterns_eligible)  # type: ignore[union-attr]

    if "promoted_total" in _COUNTERS:
        _COUNTERS["promoted_total"].inc(result.patterns_succeeded)  # type: ignore[union-attr]

    if "failed_total" in _COUNTERS:
        _COUNTERS["failed_total"].inc(result.patterns_failed)  # type: ignore[union-attr]

    if "skipped_total" in _COUNTERS:
        _COUNTERS["skipped_total"].inc(skipped_count)  # type: ignore[union-attr]

    if result.dry_run:
        if "dry_run_total" in _COUNTERS:
            _COUNTERS["dry_run_total"].inc()  # type: ignore[union-attr]
        # Gauges are not updated during dry runs — they reflect live state only.
        return

    # Update last-check gauges (non-dry-run only)
    if "last_checked" in _GAUGES:
        _GAUGES["last_checked"].set(result.patterns_checked)  # type: ignore[union-attr]

    if "last_eligible" in _GAUGES:
        _GAUGES["last_eligible"].set(result.patterns_eligible)  # type: ignore[union-attr]

    if "last_promoted" in _GAUGES:
        _GAUGES["last_promoted"].set(result.patterns_succeeded)  # type: ignore[union-attr]


__all__ = [
    "record_promotion_check_metrics",
]
