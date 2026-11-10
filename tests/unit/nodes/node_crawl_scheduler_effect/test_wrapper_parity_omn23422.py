# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the crawl scheduler handlers (OMN-2384 / OMN-23422).

Each contract-bound wrapper (``HandlerScheduleCrawlTick``,
``HandlerCrawlRequested``, ``HandlerDocumentIndexed``) must return exactly what
the preserved module function returns for the same request and the same
dependencies, and must leave the debounce state and the Kafka publisher in the
same condition.
"""

import importlib
import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.handler_crawl_scheduler import (
    handle_crawl_requested,
    handle_document_indexed,
    schedule_crawl_tick,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
    CrawlerType,
    ModelCrawlRequestedEvent,
    ModelCrawlSchedulerConfig,
)

MODULE = (
    "omniintelligence.nodes.node_crawl_scheduler_effect"
    ".handlers.handler_crawl_scheduler"
)

_PRESERVED: dict[str, Callable[..., Any]] = {
    "HandlerScheduleCrawlTick": schedule_crawl_tick,
    "HandlerCrawlRequested": handle_crawl_requested,
    "HandlerDocumentIndexed": handle_document_indexed,
}

_SOURCE = "/omninode/code/omniintelligence"
_SCOPE = "omninode/omniintelligence"
_T0 = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("00000000-0000-0000-0000-0000000000c1")
_GENERATED_ID = UUID("00000000-0000-0000-0000-0000000000c2")
_CONFIG = ModelCrawlSchedulerConfig(
    debounce_windows_seconds={
        CrawlerType.FILESYSTEM: 5,
        CrawlerType.GIT_REPO: 10,
        CrawlerType.LINEAR: 20,
        CrawlerType.WATCHDOG: 5,
    }
)


class _RecordingPublisher:
    """In-memory Kafka publisher that records messages or raises on demand."""

    def __init__(self, error: Exception | None = None) -> None:
        self.published: list[dict[str, Any]] = []
        self._error = error

    async def publish(self, topic: str, key: str, value: dict[str, object]) -> None:
        if self._error is not None:
            raise self._error
        self.published.append({"topic": topic, "key": key, "value": dict(value)})


def _state(*recorded: tuple[CrawlerType, datetime]) -> DebounceStateManager:
    state = DebounceStateManager()
    for crawler_type, when in recorded:
        state.record_trigger(source_ref=_SOURCE, crawler_type=crawler_type, now=when)
    return state


def _tick_deps(
    *recorded: tuple[CrawlerType, datetime],
    publisher: Callable[[], _RecordingPublisher | None] = _RecordingPublisher,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {
            "debounce_state": _state(*recorded),
            "config": _CONFIG,
            "kafka_publisher": publisher(),
        }

    return build


def _tick_request(
    crawl_type: CrawlerType = CrawlerType.FILESYSTEM,
    now: datetime | None = _T0,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        request: dict[str, Any] = {
            "crawl_type": crawl_type,
            "crawl_scope": _SCOPE,
            "source_ref": _SOURCE,
        }
        if now is not None:
            request["now"] = now
        return request

    return build


def _event_request(
    trigger_source: str = "manual",
    crawl_type: CrawlerType = CrawlerType.FILESYSTEM,
    now: datetime | None = _T0,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        request: dict[str, Any] = {
            "event": ModelCrawlRequestedEvent(
                crawl_type=crawl_type,
                crawl_scope=_SCOPE,
                source_ref=_SOURCE,
                correlation_id=_CORRELATION_ID,
                requested_at_utc=_T0.isoformat(),
                trigger_source=trigger_source,
            )
        }
        if now is not None:
            request["now"] = now
        return request

    return build


def _indexed_request(crawler_type: CrawlerType) -> Callable[[], dict[str, Any]]:
    return lambda: {"source_ref": _SOURCE, "crawler_type": crawler_type}


def _indexed_deps(
    *recorded: tuple[CrawlerType, datetime],
) -> Callable[[], dict[str, Any]]:
    return lambda: {"debounce_state": _state(*recorded)}


def _failing_publisher() -> _RecordingPublisher:
    return _RecordingPublisher(error=RuntimeError("broker down"))


_WITHIN_WINDOW = (CrawlerType.FILESYSTEM, _T0 - timedelta(seconds=1))
_EXPIRED_WINDOW = (CrawlerType.FILESYSTEM, _T0 - timedelta(seconds=60))

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "tick-first-emits",
        "HandlerScheduleCrawlTick",
        _tick_request(),
        _tick_deps(),
    ),
    (
        "tick-default-now-git-repo",
        "HandlerScheduleCrawlTick",
        _tick_request(CrawlerType.GIT_REPO, now=None),
        _tick_deps(),
    ),
    (
        "tick-within-window-debounced",
        "HandlerScheduleCrawlTick",
        _tick_request(),
        _tick_deps(_WITHIN_WINDOW),
    ),
    (
        "tick-after-window-emits",
        "HandlerScheduleCrawlTick",
        _tick_request(),
        _tick_deps(_EXPIRED_WINDOW),
    ),
    (
        "tick-no-publisher-error",
        "HandlerScheduleCrawlTick",
        _tick_request(),
        _tick_deps(publisher=lambda: None),
    ),
    (
        "tick-publish-raises-error",
        "HandlerScheduleCrawlTick",
        _tick_request(),
        _tick_deps(publisher=_failing_publisher),
    ),
    (
        "tick-naive-now-error",
        "HandlerScheduleCrawlTick",
        _tick_request(now=datetime(2026, 2, 20, 12, 0, 0)),
        _tick_deps(),
    ),
    (
        "requested-manual-emits",
        "HandlerCrawlRequested",
        _event_request(),
        _tick_deps(),
    ),
    (
        "requested-git-hook-default-now",
        "HandlerCrawlRequested",
        _event_request("git_hook", CrawlerType.LINEAR, now=None),
        _tick_deps(),
    ),
    (
        "requested-within-window-debounced",
        "HandlerCrawlRequested",
        _event_request("filesystem_watch"),
        _tick_deps(_WITHIN_WINDOW),
    ),
    (
        "requested-no-publisher-error",
        "HandlerCrawlRequested",
        _event_request(),
        _tick_deps(publisher=lambda: None),
    ),
    (
        "requested-publish-raises-error",
        "HandlerCrawlRequested",
        _event_request(),
        _tick_deps(publisher=_failing_publisher),
    ),
    (
        "requested-naive-now-error",
        "HandlerCrawlRequested",
        _event_request(now=datetime(2026, 2, 20, 12, 0, 0)),
        _tick_deps(),
    ),
    (
        "indexed-clears-existing",
        "HandlerDocumentIndexed",
        _indexed_request(CrawlerType.FILESYSTEM),
        _indexed_deps((CrawlerType.FILESYSTEM, _T0)),
    ),
    (
        "indexed-no-entry",
        "HandlerDocumentIndexed",
        _indexed_request(CrawlerType.GIT_REPO),
        _indexed_deps(),
    ),
    (
        "indexed-clears-only-specified-key",
        "HandlerDocumentIndexed",
        _indexed_request(CrawlerType.FILESYSTEM),
        _indexed_deps((CrawlerType.FILESYSTEM, _T0), (CrawlerType.GIT_REPO, _T0)),
    ),
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(
                    {key: _jsonable(val) for key, val in request_builder().items()},
                    default=str,
                )
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _fingerprint(deps: dict[str, Any]) -> dict[str, Any]:
    """Observable side effects: debounce entries and published messages."""
    publisher = deps.get("kafka_publisher")
    return {
        "state": dict(deps["debounce_state"]._state),
        "published": None if publisher is None else publisher.published,
    }


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, _tz: Any = None) -> datetime:
        return _T0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return alike and leave identical side effects."""
    module = importlib.import_module(MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    preserved = _PRESERVED[class_name]

    # Mask only the non-deterministic sources: uuid4() and datetime.now().
    monkeypatch.setattr(module, "uuid4", lambda: _GENERATED_ID)
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result: Any = None
    function_result: Any = None
    try:
        wrapper_result = wrapper_cls(**deps_a).handle(request_a)
        if inspect.isawaitable(wrapper_result):
            wrapper_result = await wrapper_result
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = preserved(**request_b, **deps_b)
        if inspect.isawaitable(function_result):
            function_result = await function_result
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert _fingerprint(deps_a) == _fingerprint(deps_b)
