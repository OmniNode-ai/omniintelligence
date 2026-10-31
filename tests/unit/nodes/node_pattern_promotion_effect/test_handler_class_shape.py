# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic parity proof for typed dispatch to preserved promotion logic."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
    handler_metrics,
    handler_promotion,
)
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_metrics import (
    record_promotion_check_metrics,
)
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    check_and_promote_patterns,
    promote_pattern,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelPromotionCheckResult,
    ModelPromotionResult,
)

pytestmark = pytest.mark.unit

CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000001")
PATTERN_ID = UUID("00000000-0000-0000-0000-000000000002")
SECOND_PATTERN_ID = UUID("00000000-0000-0000-0000-000000000003")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000004")
REQUEST_TIME = datetime(2025, 1, 1, tzinfo=UTC)


def _build_promotion_check_request(**kwargs: Any) -> BaseModel:
    """Load the typed request only when a parity case is dispatched."""
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckRequest,
    )

    return ModelPromotionCheckRequest(**kwargs)


PARITY_CASES: list[tuple[str, Callable[[], BaseModel]]] = [
    (
        "promotion_success",
        lambda: _build_promotion_check_request(
            min_injection_count=4,
            min_success_rate=0.5,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "promotion_dry_run",
        lambda: _build_promotion_check_request(
            dry_run=True,
            min_injection_count=4,
            min_success_rate=0.5,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "injection_threshold_not_met",
        lambda: _build_promotion_check_request(
            min_injection_count=5,
            min_success_rate=0.5,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "success_rate_threshold_not_met",
        lambda: _build_promotion_check_request(
            min_injection_count=4,
            min_success_rate=0.6,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "failure_streak_threshold_not_met",
        lambda: _build_promotion_check_request(
            min_injection_count=4,
            min_success_rate=0.5,
            max_failure_streak=1,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "kafka_unavailable",
        lambda: _build_promotion_check_request(
            min_injection_count=4,
            min_success_rate=0.5,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "publication_failure_isolated",
        lambda: _build_promotion_check_request(
            min_injection_count=4,
            min_success_rate=0.5,
            max_failure_streak=2,
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "empty_repository",
        lambda: _build_promotion_check_request(correlation_id=CORRELATION_ID),
    ),
    (
        "metrics_live_skipped",
        lambda: ModelPromotionCheckResult(
            dry_run=False,
            patterns_checked=2,
            patterns_eligible=1,
            patterns_promoted=[
                ModelPromotionResult(
                    pattern_id=PATTERN_ID,
                    pattern_signature="promotion_test",
                    from_status="provisional",
                    to_status="validated",
                    reason="promotion_skipped: kafka_producer_unavailable",
                    gate_snapshot=handler_promotion.build_gate_snapshot({}),
                    dry_run=False,
                )
            ],
            correlation_id=CORRELATION_ID,
        ),
    ),
    (
        "metrics_dry_run",
        lambda: ModelPromotionCheckResult(
            dry_run=True,
            patterns_checked=2,
            patterns_eligible=1,
            correlation_id=CORRELATION_ID,
        ),
    ),
]


class MockPatternRepository:
    """In-memory records and query history, matching the node test mocks."""

    def __init__(self, patterns: list[Mapping[str, Any]]) -> None:
        self.patterns = patterns
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        self.queries.append(query)
        return self.patterns

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None

    async def execute(self, query: str, *args: object) -> str:
        raise AssertionError("Promotion must use lifecycle events")


class MockKafkaPublisher:
    """Capture events or simulate the first publication failing."""

    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.attempts = 0
        self.events: list[tuple[str, str, dict[str, object]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, object]) -> None:
        self.attempts += 1
        if self.fail_first and self.attempts == 1:
            raise OSError("Publish failed")
        self.events.append((topic, key, value))


@pytest.fixture
def pattern() -> dict[str, Any]:
    """Nondefault gate values detect omitted request threshold forwarding."""
    return {
        "id": PATTERN_ID,
        "pattern_signature": "promotion_test",
        "injection_count_rolling_20": 4,
        "success_count_rolling_20": 2,
        "failure_count_rolling_20": 2,
        "failure_streak": 1,
    }


@pytest.fixture(autouse=True)
def stable_event_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix event context and isolate metrics from process-wide registration."""
    clock = Mock(wraps=datetime)
    clock.now.return_value = REQUEST_TIME
    monkeypatch.setattr(handler_promotion, "datetime", clock)
    monkeypatch.setattr(handler_promotion, "uuid4", lambda: EVENT_ID)
    monkeypatch.setattr(handler_metrics, "_init_metrics", lambda: None)
    monkeypatch.setattr(handler_metrics, "_COUNTERS", {})
    monkeypatch.setattr(handler_metrics, "_GAUGES", {})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "build_request"),
    PARITY_CASES,
    ids=[case_id for case_id, _ in PARITY_CASES],
)
async def test_canonical_dispatch_matches_preserved_core(
    case_id: str,
    build_request: Callable[[], BaseModel],
    pattern: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare results and observable effects on equivalent fresh fakes."""
    class_name = (
        "HandlerPromotionMetrics"
        if case_id.startswith("metrics_")
        else "HandlerPromotion"
    )
    module_name = (
        "omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_metrics"
        if case_id.startswith("metrics_")
        else "omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion"
    )
    module = importlib.import_module(module_name)
    handler_cls = getattr(module, class_name, None)
    assert handler_cls is not None, f"{class_name} is missing from {module_name}"

    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckRequest,
    )

    case_request = build_request()
    if isinstance(case_request, ModelPromotionCheckResult):
        observations = []
        for dispatch in (
            handler_cls().handle,
            record_promotion_check_metrics,
        ):
            counters = {
                name: Mock()
                for name in (
                    "patterns_total",
                    "eligible_total",
                    "promoted_total",
                    "failed_total",
                    "skipped_total",
                    "dry_run_total",
                )
            }
            gauges = {
                name: Mock()
                for name in ("last_checked", "last_eligible", "last_promoted")
            }
            monkeypatch.setattr(handler_metrics, "_COUNTERS", counters)
            monkeypatch.setattr(handler_metrics, "_GAUGES", gauges)
            result = dispatch(case_request)
            observations.append(
                (
                    result,
                    {
                        name: mock.mock_calls[:]
                        for name, mock in (counters | gauges).items()
                    },
                )
            )
            counters["patterns_total"].inc.assert_called_once_with(2)
            counters["eligible_total"].inc.assert_called_once_with(1)
            counters["skipped_total"].inc.assert_called_once_with(
                0 if case_request.dry_run else 1
            )
            if case_request.dry_run:
                counters["dry_run_total"].inc.assert_called_once_with()
                gauges["last_checked"].set.assert_not_called()
            else:
                gauges["last_checked"].set.assert_called_once_with(2)
        assert observations[0] == observations[1]
        return

    assert isinstance(case_request, ModelPromotionCheckRequest)
    patterns = (
        []
        if case_id == "empty_repository"
        else [pattern, {**pattern, "id": SECOND_PATTERN_ID}]
    )
    class_repository = MockPatternRepository([dict(row) for row in patterns])
    function_repository = MockPatternRepository([dict(row) for row in patterns])
    class_producer = (
        None
        if case_id == "kafka_unavailable"
        else MockKafkaPublisher(fail_first=case_id == "publication_failure_isolated")
    )
    function_producer = (
        None
        if case_id == "kafka_unavailable"
        else MockKafkaPublisher(fail_first=case_id == "publication_failure_isolated")
    )

    actual = await handler_cls(class_repository, class_producer).handle(case_request)
    expected = await check_and_promote_patterns(
        function_repository,
        function_producer,
        dry_run=case_request.dry_run,
        min_injection_count=case_request.min_injection_count,
        min_success_rate=case_request.min_success_rate,
        max_failure_streak=case_request.max_failure_streak,
        correlation_id=case_request.correlation_id,
    )

    assert actual.model_dump() == expected.model_dump()
    assert actual.patterns_checked == len(patterns)
    assert actual.correlation_id == CORRELATION_ID
    assert class_repository.queries == function_repository.queries
    rejected = case_id.endswith("threshold_not_met") or case_id == "empty_repository"
    assert actual.patterns_eligible == (0 if rejected else 2)
    if class_producer is not None and function_producer is not None:
        assert class_producer.events == function_producer.events
        assert class_producer.attempts == function_producer.attempts
        assert len(class_producer.events) == {
            "promotion_success": 2,
            "publication_failure_isolated": 1,
        }.get(case_id, 0)
        for _, _, event in class_producer.events:
            assert event["correlation_id"] == str(CORRELATION_ID)
    if case_id == "promotion_success":
        assert actual.patterns_succeeded == 2
    elif case_id == "promotion_dry_run":
        assert all(result.dry_run for result in actual.patterns_promoted)
    elif case_id == "kafka_unavailable":
        assert all(
            result.reason == "promotion_skipped: kafka_producer_unavailable"
            for result in actual.patterns_promoted
        )
    elif case_id == "publication_failure_isolated":
        assert actual.patterns_failed == actual.patterns_succeeded == 1
        assert actual.patterns_promoted[0].reason.startswith(
            "promotion_failed: OSError:"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_promote_matches_preserved_core(
    available: bool, pattern: dict[str, Any]
) -> None:
    """Single promotion preserves events, trace context and Kafka degradation."""
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        HandlerPromotion,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotePatternRequest,
    )

    class_producer = MockKafkaPublisher() if available else None
    function_producer = MockKafkaPublisher() if available else None
    request = ModelPromotePatternRequest(
        pattern_id=PATTERN_ID, pattern_data=pattern, correlation_id=CORRELATION_ID
    )

    actual = await HandlerPromotion(MockPatternRepository([]), class_producer).promote(
        request
    )
    expected = await promote_pattern(
        function_producer,
        request.pattern_id,
        request.pattern_data,
        request.correlation_id,
    )

    assert actual.model_dump() == expected.model_dump()
    assert (actual.promoted_at is not None) == available
    if class_producer is not None and function_producer is not None:
        assert class_producer.events == function_producer.events
        assert class_producer.events[0][2]["correlation_id"] == str(CORRELATION_ID)


@pytest.mark.asyncio
async def test_promote_preserves_publication_exception(pattern: dict[str, Any]) -> None:
    """Single promotion propagates failures for its batch caller to isolate."""
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        HandlerPromotion,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotePatternRequest,
    )

    request = ModelPromotePatternRequest(pattern_id=PATTERN_ID, pattern_data=pattern)
    with pytest.raises(OSError, match="Publish failed"):
        await HandlerPromotion(
            MockPatternRepository([]), MockKafkaPublisher(fail_first=True)
        ).promote(request)
    with pytest.raises(OSError, match="Publish failed"):
        await promote_pattern(
            MockKafkaPublisher(fail_first=True),
            request.pattern_id,
            request.pattern_data,
        )


@pytest.mark.asyncio
async def test_handle_preserves_repository_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Infrastructure errors propagate from both dispatch paths."""
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        HandlerPromotion,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckRequest,
    )

    class_repository = MockPatternRepository([])
    function_repository = MockPatternRepository([])
    monkeypatch.setattr(
        class_repository, "fetch", Mock(side_effect=OSError("Fetch failed"))
    )
    monkeypatch.setattr(
        function_repository, "fetch", Mock(side_effect=OSError("Fetch failed"))
    )
    request = ModelPromotionCheckRequest(correlation_id=CORRELATION_ID)
    with pytest.raises(OSError, match="Fetch failed"):
        await HandlerPromotion(class_repository).handle(request)
    with pytest.raises(OSError, match="Fetch failed"):
        await check_and_promote_patterns(
            function_repository, correlation_id=request.correlation_id
        )


def test_metrics_recording_failure_stays_best_effort(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Both entry points retain the warning and suppress metric errors."""
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        HandlerPromotionMetrics,
    )

    monkeypatch.setattr(
        handler_metrics, "_record", Mock(side_effect=OSError("Metrics failed"))
    )
    request = ModelPromotionCheckResult(
        dry_run=False,
        patterns_checked=0,
        patterns_eligible=0,
        correlation_id=CORRELATION_ID,
    )

    assert HandlerPromotionMetrics().handle(request) is None
    assert record_promotion_check_metrics(request) is None
    assert (
        caplog.messages
        == ["Failed to record promotion check metrics: Metrics failed"] * 2
    )
