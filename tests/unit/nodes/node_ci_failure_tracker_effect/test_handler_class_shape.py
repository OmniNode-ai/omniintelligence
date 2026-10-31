# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic parity checks against the preserved module functions."""

import importlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.constants import TOPIC_CI_DEBUG_ESCALATION_V1
from omniintelligence.models.events.model_ci_debug_escalation_event import (
    ModelCiDebugEscalationEvent,
)
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_streak import (
    get_current_streak,
    increment_streak,
    reset_streak,
)
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_trigger_record import (
    handle_trigger_record,
)


def _build_streak_request(sha: str = "abc123") -> BaseModel:
    from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
        ModelStreakIncrementRequest,
    )

    return ModelStreakIncrementRequest(repo="OmniNode-ai/test", branch="main", sha=sha)


def _build_trigger_request(error_classification: str = "test_failure") -> BaseModel:
    from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
        ModelTriggerRecordRequest,
    )

    return ModelTriggerRecordRequest(
        repo="OmniNode-ai/test",
        branch="main",
        sha="deadbeef",
        failure_fingerprint="fp-abc",
        error_classification=error_classification,
        streak_threshold=3,
        correlation_id="00000000-0000-0000-0000-000000000001",
    )


_FIXED_TIME = datetime(2025, 1, 1, tzinfo=UTC)
_ESCALATION_ID = UUID("00000000-0000-0000-0000-000000000002")
_TRIGGER_ID = "00000000-0000-0000-0000-000000000003"

PARITY_CASES: list[tuple[str, Callable[[], BaseModel]]] = [
    ("streak-new", _build_streak_request),
    ("streak-existing", lambda: _build_streak_request(sha="def456")),
    ("trigger-no-streak", _build_trigger_request),
    ("trigger-below-threshold", _build_trigger_request),
    ("trigger-at-threshold", _build_trigger_request),
    ("trigger-above-threshold", _build_trigger_request),
    (
        "trigger-empty-classification",
        lambda: _build_trigger_request(error_classification=""),
    ),
    ("trigger-publish-failure", _build_trigger_request),
    ("trigger-store-failure", _build_trigger_request),
]

_STREAK_COUNTS: dict[str, int | None] = {
    "streak-new": 0,
    "streak-existing": 4,
    "trigger-no-streak": None,
    "trigger-below-threshold": 2,
    "trigger-at-threshold": 3,
    "trigger-above-threshold": 5,
    "trigger-empty-classification": 3,
    "trigger-publish-failure": 3,
    "trigger-store-failure": None,
}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "build_request"),
    PARITY_CASES,
    ids=[case_id for case_id, _ in PARITY_CASES],
)
async def test_canonical_dispatch_matches_preserved_core(
    case_id: str, build_request: Callable[[], BaseModel]
) -> None:
    """Both entry points return or raise alike and make identical store/event calls."""
    module_name = "omniintelligence.nodes.node_ci_failure_tracker_effect.handlers." + (
        "handler_streak" if case_id.startswith("streak-") else "handler_trigger_record"
    )
    class_name = (
        "HandlerStreak" if case_id.startswith("streak-") else "HandlerTriggerRecord"
    )
    module = importlib.import_module(module_name)
    handler_cls = getattr(module, class_name, None)
    assert handler_cls is not None, f"{class_name} is missing from {module_name}"

    from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
        ModelStreakIncrementRequest,
        ModelTriggerRecordRequest,
        ModelTriggerRecordResponse,
    )

    request = build_request()
    assert isinstance(request, (ModelStreakIncrementRequest, ModelTriggerRecordRequest))
    class_store, core_store = AsyncMock(), AsyncMock()
    class_producer, core_producer = AsyncMock(), AsyncMock()
    streak_count = _STREAK_COUNTS[case_id]
    trigger = {"id": _TRIGGER_ID, "observed_bad_sha": request.sha}
    for store, producer in (
        (class_store, class_producer),
        (core_store, core_producer),
    ):
        store.get_streak.return_value = (
            None if streak_count is None else {"streak_count": streak_count}
        )
        store.upsert_streak.return_value = {
            "repo": request.repo,
            "branch": request.branch,
            "last_sha": request.sha,
            "streak_count": (streak_count or 0) + 1,
        }
        store.insert_trigger_record.return_value = trigger.copy()
        if case_id == "trigger-publish-failure":
            producer.publish.side_effect = RuntimeError("publish failed")
        if case_id == "trigger-store-failure":
            store.get_streak.side_effect = RuntimeError("store failed")

    if isinstance(request, ModelStreakIncrementRequest):
        result = await handler_cls(class_store).handle(request)
        core_result = await increment_streak(**request.model_dump(), store=core_store)
        assert result == core_result == class_store.upsert_streak.return_value
        assert class_store.mock_calls == core_store.mock_calls
        class_store.upsert_streak.assert_awaited_once_with(
            repo=request.repo, branch=request.branch, sha=request.sha
        )
        return

    assert isinstance(request, ModelTriggerRecordRequest)
    if case_id == "trigger-store-failure":
        with pytest.raises(RuntimeError, match=r"^store failed$"):
            await handler_cls(class_store, class_producer).handle(request)
        with pytest.raises(RuntimeError, match=r"^store failed$"):
            await handle_trigger_record(
                **request.model_dump(), store=core_store, kafka_producer=core_producer
            )
        assert class_store.mock_calls == core_store.mock_calls
        class_store.insert_ci_failure_event.assert_not_awaited()
        class_producer.publish.assert_not_awaited()
        core_producer.publish.assert_not_awaited()
        return

    without_producer = case_id in {"trigger-no-streak", "trigger-above-threshold"}
    with (
        patch("datetime.datetime", wraps=datetime) as fixed_datetime,
        patch("uuid.uuid4", return_value=_ESCALATION_ID),
    ):
        fixed_datetime.now.return_value = _FIXED_TIME
        response = await handler_cls(
            class_store, None if without_producer else class_producer
        ).handle(request)
        core_result = await handle_trigger_record(
            **request.model_dump(),
            store=core_store,
            kafka_producer=None if without_producer else core_producer,
        )

    expected = (
        trigger
        if streak_count is not None and streak_count >= request.streak_threshold
        else None
    )
    assert response == ModelTriggerRecordResponse(trigger=core_result)
    assert response.trigger == expected
    assert class_store.mock_calls == core_store.mock_calls
    assert class_producer.mock_calls == core_producer.mock_calls
    class_store.insert_ci_failure_event.assert_awaited_once_with(
        repo=request.repo,
        branch=request.branch,
        sha=request.sha,
        failure_fingerprint=request.failure_fingerprint,
        error_classification=request.error_classification,
        streak_snapshot=streak_count or 0,
    )
    if expected is None:
        class_store.insert_trigger_record.assert_not_awaited()
        class_producer.publish.assert_not_awaited()
    else:
        class_store.insert_trigger_record.assert_awaited_once_with(
            repo=request.repo,
            branch=request.branch,
            failure_fingerprint=request.failure_fingerprint,
            error_classification=request.error_classification,
            observed_bad_sha=request.sha,
            streak_count_at_trigger=streak_count,
        )
        if without_producer:
            class_producer.publish.assert_not_awaited()
        else:
            class_producer.publish.assert_awaited_once_with(
                topic=TOPIC_CI_DEBUG_ESCALATION_V1,
                key=f"{request.repo}/{request.branch}",
                value=ModelCiDebugEscalationEvent(
                    escalation_id=str(_ESCALATION_ID),
                    correlation_id=request.correlation_id,
                    repo=request.repo,
                    branch=request.branch,
                    ci_run_url="",
                    failure_type=request.error_classification or "unknown",
                    consecutive_failures=streak_count,
                    escalated_at=_FIXED_TIME,
                ).model_dump(mode="json"),
            )


@pytest.mark.unit
async def test_streak_reset_matches_preserved_core() -> None:
    """Reset forwards the same arguments without changing handler state."""
    from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers import (
        HandlerStreak,
    )
    from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
        ModelStreakResetRequest,
    )

    request = ModelStreakResetRequest(repo="OmniNode-ai/test", branch="main")
    class_store, core_store = AsyncMock(), AsyncMock()
    handler = HandlerStreak(class_store)
    state = vars(handler).copy()

    result = await handler.reset(request)
    core_result = await reset_streak(**request.model_dump(), store=core_store)

    assert result is core_result is None
    assert class_store.mock_calls == core_store.mock_calls
    class_store.reset_streak.assert_awaited_once_with(
        repo=request.repo, branch=request.branch
    )
    assert vars(handler) == state


@pytest.mark.unit
@pytest.mark.parametrize("row, expected", [(None, 0), ({"streak_count": "5"}, 5)])
async def test_streak_current_matches_preserved_core(
    row: dict[str, Any] | None, expected: int
) -> None:
    """Query preserves absent-row and numeric conversion behavior without mutation."""
    from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers import (
        HandlerStreak,
    )
    from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
        ModelStreakQueryRequest,
    )

    request = ModelStreakQueryRequest(repo="OmniNode-ai/test", branch="main")
    class_store, core_store = AsyncMock(), AsyncMock()
    class_store.get_streak.return_value = row
    core_store.get_streak.return_value = row.copy() if row is not None else None
    handler = HandlerStreak(class_store)
    state = vars(handler).copy()

    result = await handler.current(request)
    core_result = await get_current_streak(**request.model_dump(), store=core_store)

    assert result == core_result == expected
    assert class_store.mock_calls == core_store.mock_calls
    class_store.get_streak.assert_awaited_once_with(
        repo=request.repo, branch=request.branch
    )
    assert vars(handler) == state
