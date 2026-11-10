# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound watchdog wrappers match the preserved functions.

``HandlerStartWatching`` and ``HandlerStopWatching`` splat a request mapping
into ``start_watching`` and ``stop_watching``. Both run against the same
process-wide observer registry, so every run starts from a cleared registry
plus the case's preset observer, and the registry, the injected fakes and the
result must match after each run. The result timestamp is pinned by patching
the result model module's clock.

Ticket: OMN-23422
"""

import asyncio
import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_watchdog_effect.handlers.handler_watchdog import (
    start_watching,
    stop_watching,
)
from omniintelligence.nodes.node_watchdog_effect.models import (
    EnumWatchdogObserverType,
    ModelWatchdogConfig,
)
from omniintelligence.nodes.node_watchdog_effect.registry import (
    registry_watchdog_effect,
)
from omniintelligence.nodes.node_watchdog_effect.registry.registry_watchdog_effect import (
    RegistryWatchdogEffect,
)

MODULE = "omniintelligence.nodes.node_watchdog_effect.handlers.handler_watchdog"
RESULT_MODULE = (
    "omniintelligence.nodes.node_watchdog_effect.models.model_watchdog_result"
)
START = "HandlerStartWatching"
STOP = "HandlerStopWatching"

_PRESERVED: dict[str, Callable[..., Any]] = {
    START: start_watching,
    STOP: stop_watching,
}

_FIXED_TIME = datetime(2025, 1, 1, tzinfo=UTC)
_CORRELATION_ID = UUID("00000000-0000-0000-0000-0000000000c1")
_POLLING = EnumWatchdogObserverType.POLLING


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeObserver:
    """Observer fake that records lifecycle calls and can fail on demand."""

    def __init__(
        self,
        *,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
        join_error: Exception | None = None,
        schedule_error: Exception | None = None,
        stays_alive: bool = False,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.join_error = join_error
        self.schedule_error = schedule_error
        self.stays_alive = stays_alive
        self.started = False
        self.stopped = False
        self.join_timeouts: list[float | None] = []
        self.scheduled: list[tuple[str, bool, str]] = []
        self.handlers: list[Any] = []

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started = True

    def stop(self) -> None:
        if self.stop_error is not None:
            raise self.stop_error
        self.stopped = True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)
        if self.join_error is not None:
            raise self.join_error

    def is_alive(self) -> bool:
        return self.stays_alive or (self.started and not self.stopped)

    def schedule(self, handler: Any, path: str, recursive: bool = True) -> None:
        if self.schedule_error is not None:
            raise self.schedule_error
        self.handlers.append(handler)
        self.scheduled.append((path, recursive, type(handler).__name__))

    def snapshot(self) -> dict[str, Any]:
        return {
            "started": self.started,
            "stopped": self.stopped,
            "join_timeouts": list(self.join_timeouts),
            "scheduled": list(self.scheduled),
        }


class FakeObserverFactory:
    """Zero-argument observer factory that records the observers it creates."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
        observer_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.error = error
        self.observer_kwargs = observer_kwargs or {}
        self.created: list[FakeObserver] = []

    def __call__(self) -> tuple[FakeObserver, EnumWatchdogObserverType]:
        if self.error is not None:
            raise self.error
        observer = FakeObserver(**self.observer_kwargs)
        self.created.append(observer)
        return observer, _POLLING


class FakePublisher:
    """Kafka publisher fake that records published messages."""

    def __init__(self, fail_for: str | None = None) -> None:
        self.fail_for = fail_for
        self.calls: list[dict[str, Any]] = []

    async def publish(self, topic: str, key: str, value: object) -> None:
        self.calls.append({"topic": topic, "key": key, "value": value})
        if key == self.fail_for:
            raise ConnectionError("broker unavailable")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def _config(*paths: str) -> ModelWatchdogConfig:
    return ModelWatchdogConfig(
        watched_paths=paths or ("/", "/usr"), crawl_scope="omninode/test"
    )


def _start_request(config: ModelWatchdogConfig | None = None) -> dict[str, Any]:
    return {
        "config": config if config is not None else _config(),
        "correlation_id": _CORRELATION_ID,
    }


def _stop_request() -> dict[str, Any]:
    return {"correlation_id": _CORRELATION_ID}


def _start_deps(
    *,
    publisher: bool = True,
    error: Exception | None = None,
    **observer_kwargs: Any,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {
            "kafka_publisher": FakePublisher(fail_for="/watched/broken.md")
            if publisher
            else None,
            "observer_factory": FakeObserverFactory(
                error=error, observer_kwargs=observer_kwargs
            ),
        }

    return build


def _no_deps() -> dict[str, Any]:
    return {}


# Observer preset into the registry before a run (None means an empty registry).
_PRESETS: dict[str, Callable[[], FakeObserver]] = {
    "start-already-running": lambda: FakeObserver(),
    "stop-running-observer": lambda: FakeObserver(),
    "stop-observer-stop-raises": lambda: FakeObserver(
        stop_error=RuntimeError("stop failed")
    ),
    "stop-join-raises": lambda: FakeObserver(join_error=OSError("join failed")),
    "stop-thread-still-alive": lambda: FakeObserver(stays_alive=True),
}

PARITY_CASES: list[
    tuple[str, str, Callable[[], dict[str, Any]], Callable[[], dict[str, Any]]]
] = [
    ("start-with-publisher", START, _start_request, _start_deps()),
    ("start-without-publisher", START, _start_request, _start_deps(publisher=False)),
    (
        "start-single-path",
        START,
        lambda: _start_request(_config("/usr")),
        _start_deps(),
    ),
    ("start-already-running", START, _start_request, _start_deps()),
    (
        "start-missing-path",
        START,
        lambda: _start_request(_config("/", "/nonexistent-omn23422-path")),
        _start_deps(),
    ),
    (
        "start-factory-raises",
        START,
        _start_request,
        _start_deps(error=RuntimeError("no observer available")),
    ),
    (
        "start-observer-start-raises",
        START,
        _start_request,
        _start_deps(start_error=RuntimeError("start failed")),
    ),
    (
        "start-schedule-raises",
        START,
        _start_request,
        _start_deps(schedule_error=OSError("cannot watch")),
    ),
    ("stop-no-observer", STOP, _stop_request, _no_deps),
    ("stop-running-observer", STOP, _stop_request, _no_deps),
    ("stop-observer-stop-raises", STOP, _stop_request, _no_deps),
    ("stop-join-raises", STOP, _stop_request, _no_deps),
    ("stop-thread-still-alive", STOP, _stop_request, _no_deps),
]


_EXPECTED_STATUS: dict[str, str] = {
    "start-with-publisher": "started",
    "start-without-publisher": "started",
    "start-single-path": "started",
    "start-already-running": "started",
    "start-missing-path": "error",
    "start-factory-raises": "error",
    "start-observer-start-raises": "error",
    "start-schedule-raises": "error",
    "stop-no-observer": "stopped",
    "stop-running-observer": "stopped",
    "stop-observer-stop-raises": "error",
    "stop-join-raises": "stopped",
    "stop-thread-still-alive": "stopped",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(str(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(_jsonable(request_builder()), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


_EVENTS = [
    SimpleNamespace(is_directory=False, src_path="/watched/doc.md"),
    SimpleNamespace(is_directory=False, src_path="/watched/notes.swp"),
    SimpleNamespace(is_directory=True, src_path="/watched/subdir"),
    SimpleNamespace(is_directory=False, src_path=""),
    SimpleNamespace(is_directory=False, src_path="/watched/broken.md"),
]


def _registry_snapshot() -> dict[str, Any]:
    observer = RegistryWatchdogEffect.get_observer()
    config = RegistryWatchdogEffect.get_config()
    return {
        "keys": sorted(registry_watchdog_effect._HANDLER_STORAGE),
        "observer": observer.snapshot() if observer is not None else None,
        "observer_type": RegistryWatchdogEffect.get_observer_type(),
        "watched_paths": config.watched_paths if config is not None else None,
    }


counter = {"n": 0}


def fake_uuid4() -> UUID:
    """Deterministic stand-in for the handler module's ``uuid4``."""
    counter["n"] += 1
    return UUID(f"00000000-0000-0000-0000-{0xD00 + counter['n']:012d}")


async def _run(
    case_id: str,
    call: Callable[[], Any],
    deps: dict[str, Any],
) -> dict[str, Any]:
    """Run one entry point from a prepared registry; return everything observable."""
    RegistryWatchdogEffect.clear()
    counter["n"] = 0
    preset = _PRESETS.get(case_id)
    preset_observer = preset() if preset is not None else None
    if preset_observer is not None:
        RegistryWatchdogEffect.register_observer(
            preset_observer, _POLLING, _config("/usr")
        )
    error: Exception | None = None
    result = None
    try:
        result = await call()
    except Exception as exc:
        error = exc
    factory = deps.get("observer_factory")
    if factory is not None and factory.created and factory.created[0].handlers:
        # Deliver filesystem events through the handler the entry point scheduled.
        for event in _EVENTS:
            factory.created[0].handlers[0].dispatch(event)
        for _ in range(5):
            await asyncio.sleep(0)
    snapshot = {
        "result": result,
        "error": (type(error), str(error)) if error is not None else None,
        "registry": _registry_snapshot(),
        "preset_observer": (
            preset_observer.snapshot() if preset_observer is not None else None
        ),
        "created": [o.snapshot() for o in deps["observer_factory"].created]
        if "observer_factory" in deps
        else None,
        "published": deps["kafka_publisher"].calls
        if deps.get("kafka_publisher") is not None
        else None,
    }
    RegistryWatchdogEffect.clear()
    return snapshot


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
    """The wrapper returns exactly what the preserved function returns."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, *_args: Any, **_kwargs: Any) -> datetime:
            return _FIXED_TIME

    monkeypatch.setattr(
        importlib.import_module(RESULT_MODULE), "datetime", _FixedDatetime
    )
    handler_module = importlib.import_module(MODULE)
    monkeypatch.setattr(handler_module, "datetime", _FixedDatetime)
    monkeypatch.setattr(handler_module, "uuid4", fake_uuid4)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()
    preserved = _PRESERVED[class_name]

    try:
        wrapper_run = await _run(
            case_id, lambda: wrapper_cls(**deps_a).handle(request_a), deps_a
        )
        function_run = await _run(
            case_id, lambda: preserved(**request_b, **deps_b), deps_b
        )
    finally:
        RegistryWatchdogEffect.clear()

    assert wrapper_run == function_run
    assert wrapper_run["error"] is None
    assert wrapper_run["result"].status.value == _EXPECTED_STATUS[case_id]
    if case_id == "start-with-publisher":
        assert [call["key"] for call in wrapper_run["published"]] == [
            "/watched/doc.md",
            "/watched/broken.md",
        ]
