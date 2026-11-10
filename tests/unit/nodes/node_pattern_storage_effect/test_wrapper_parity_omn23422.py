# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound pattern-storage wrappers match the preserved functions.

``HandlerConsumeDiscovered``, ``HandlerPromotePattern`` and
``HandlerStorePattern`` forward to ``handle_consume_discovered``,
``handle_promote_pattern`` and ``handle_store_pattern``. Each wrapper is run
against identical requests and fresh in-memory stores/state managers; the
results (or raised errors) and the final fake state must be identical. The
handler modules' clock and ``uuid4`` names are patched with fixed values.

Ticket: OMN-23422
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_consume_discovered import (
    handle_consume_discovered,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
    handle_promote_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    handle_store_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
)
from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_metrics_snapshot import (
    ModelPatternMetricsSnapshot,
)
from omniintelligence.testing import (
    MockPatternStateManager,
    MockPatternStore,
    make_discovered_event,
)

_HANDLERS = "omniintelligence.nodes.node_pattern_storage_effect.handlers."
CONSUME_MODULE = _HANDLERS + "handler_consume_discovered"
PROMOTE_MODULE = _HANDLERS + "handler_promote_pattern"
STORE_MODULE = _HANDLERS + "handler_store_pattern"

CONSUME = "HandlerConsumeDiscovered"
PROMOTE = "HandlerPromotePattern"
STORE = "HandlerStorePattern"

_WRAPPER_MODULES = {
    CONSUME: CONSUME_MODULE,
    PROMOTE: PROMOTE_MODULE,
    STORE: STORE_MODULE,
}
_PRESERVED: dict[str, Callable[..., Any]] = {
    CONSUME: handle_consume_discovered,
    PROMOTE: handle_promote_pattern,
    STORE: handle_store_pattern,
}
# Wrappers whose forwarding line splats ``**request`` (the request is a dict).
_SPLAT_WRAPPERS = frozenset({PROMOTE})

_FIXED_TIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
_EARLIER = datetime(2024, 12, 31, 8, 0, 0, tzinfo=UTC)
_PATTERN_ID = UUID("00000000-0000-0000-0000-000000000001")
_SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
_CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000003")
_OTHER_ID = UUID("00000000-0000-0000-0000-000000000004")
_HASH = "hash-abc"
_DOMAIN = "code_patterns"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FailingPatternStore(MockPatternStore):
    """Mock store that raises from one named method."""

    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on

    async def check_exists_by_id(self, *args: Any, **kwargs: Any) -> UUID | None:
        if self.fail_on == "check_exists_by_id":
            raise RuntimeError("check_exists_by_id failed")
        return await super().check_exists_by_id(*args, **kwargs)

    async def store_pattern(self, **kwargs: Any) -> UUID:
        if self.fail_on == "store_pattern":
            raise RuntimeError("store_pattern failed")
        return await super().store_pattern(**kwargs)


class FailingStateManager(MockPatternStateManager):
    """Mock state manager that raises from one named method."""

    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on

    async def update_state(self, *args: Any, **kwargs: Any) -> None:
        if self.fail_on == "update_state":
            raise RuntimeError("update_state failed")
        await super().update_state(*args, **kwargs)

    async def record_transition(self, *args: Any, **kwargs: Any) -> None:
        if self.fail_on == "record_transition":
            raise RuntimeError("record_transition failed")
        await super().record_transition(*args, **kwargs)


def _seed_pattern(
    store: MockPatternStore,
    *,
    pattern_id: UUID = _PATTERN_ID,
    stored_at: datetime | None = _EARLIER,
    version: int = 1,
) -> None:
    record: dict[str, Any] = {
        "pattern_id": pattern_id,
        "signature": "seeded",
        "signature_hash": _HASH,
        "domain": _DOMAIN,
        "version": version,
        "confidence": 0.9,
        "quality_score": 0.5,
        "state": EnumPatternState.CANDIDATE,
        "is_current": True,
        "metadata": {},
    }
    if stored_at is not None:
        record["stored_at"] = stored_at
    store.patterns[pattern_id] = record
    store.idempotency_map[(pattern_id, _HASH)] = pattern_id
    store._version_tracker[(_DOMAIN, _HASH)] = version


def _store_deps(
    *,
    seed: dict[str, Any] | None = None,
    fail_on: str | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        store = FailingPatternStore(fail_on) if fail_on else MockPatternStore()
        if seed is not None:
            _seed_pattern(store, **seed)
        return {"pattern_store": store, "conn": None}

    return build


def _state_deps(
    states: dict[UUID, EnumPatternState] | None = None,
    *,
    fail_on: str | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        manager = FailingStateManager(fail_on) if fail_on else MockPatternStateManager()
        for pattern_id, state in (states or {}).items():
            manager.set_state(pattern_id, state)
        return {"state_manager": manager, "conn": None}

    return build


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------


def _event(**overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "discovery_id": _PATTERN_ID,
        "source_session_id": _SESSION_ID,
        "correlation_id": _CORRELATION_ID,
        "discovered_at": _FIXED_TIME,
        "signature_hash": _HASH,
        "domain": _DOMAIN,
    }
    fields.update(overrides)
    return make_discovered_event(**fields)


def _storage_input(**overrides: Any) -> ModelPatternStorageInput:
    fields: dict[str, Any] = {
        "pattern_id": _PATTERN_ID,
        "signature": "def.*return.*None",
        "signature_hash": _HASH,
        "domain": _DOMAIN,
        "confidence": 0.85,
        "correlation_id": _CORRELATION_ID,
        "metadata": ModelPatternStorageMetadata(
            source_run_id="run-1",
            actor="unit",
            learning_context="parity",
            tags=["a", "b"],
            additional_attributes={"k": "v"},
        ),
    }
    fields.update(overrides)
    return ModelPatternStorageInput(**fields)


def _low_confidence_input() -> ModelPatternStorageInput:
    """Bypass model validation to reach the handler's own governance layer."""
    return ModelPatternStorageInput.model_construct(
        pattern_id=_PATTERN_ID,
        signature="def.*return.*None",
        signature_hash=_HASH,
        domain=_DOMAIN,
        confidence=0.3,
        correlation_id=_CORRELATION_ID,
        version=1,
        metadata=ModelPatternStorageMetadata(),
        learned_at=None,
    )


def _promote_request(
    to_state: EnumPatternState,
    *,
    pattern_id: UUID = _PATTERN_ID,
    **extra: Any,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "pattern_id": pattern_id,
        "to_state": to_state,
        "reason": "met criteria",
    }
    request.update(extra)
    return request


_METRICS = ModelPatternMetricsSnapshot(
    confidence=0.9, match_count=12, success_rate=0.95, validation_count=3
)
_CANDIDATE = EnumPatternState.CANDIDATE
_PROVISIONAL = EnumPatternState.PROVISIONAL
_VALIDATED = EnumPatternState.VALIDATED

PARITY_CASES: list[tuple[str, str, Callable[[], Any], Callable[[], dict[str, Any]]]] = [
    # --- HandlerConsumeDiscovered -------------------------------------------
    ("consume-new-pattern", CONSUME, _event, _store_deps()),
    (
        "consume-idempotent-replay",
        CONSUME,
        _event,
        _store_deps(seed={"stored_at": _EARLIER}),
    ),
    (
        "consume-replay-without-stored-at",
        CONSUME,
        _event,
        _store_deps(seed={"stored_at": None}),
    ),
    (
        "consume-new-version-in-lineage",
        CONSUME,
        lambda: _event(discovery_id=_OTHER_ID),
        _store_deps(seed={"version": 2}),
    ),
    (
        "consume-metadata-mapping",
        CONSUME,
        lambda: _event(
            source_agent=None,
            metadata={
                "source_agent": 42,
                "actor": "attacker",
                "tags": "dropped",
                "keep": "yes",
                "non_string": 7,
            },
        ),
        _store_deps(),
    ),
    (
        "consume-source-agent-wins",
        CONSUME,
        lambda: _event(source_agent="agent-x", metadata={"keep": "yes"}),
        _store_deps(),
    ),
    (
        "consume-governance-rejection",
        CONSUME,
        lambda: _event(pattern_signature="   "),
        _store_deps(),
    ),
    (
        "consume-store-raises",
        CONSUME,
        _event,
        _store_deps(fail_on="store_pattern"),
    ),
    # --- HandlerStorePattern -------------------------------------------------
    ("store-new-pattern", STORE, _storage_input, _store_deps()),
    (
        "store-idempotent-return",
        STORE,
        _storage_input,
        _store_deps(seed={"stored_at": _EARLIER}),
    ),
    (
        "store-idempotent-fallback-timestamp",
        STORE,
        _storage_input,
        _store_deps(seed={"stored_at": None}),
    ),
    (
        "store-new-version-transition",
        STORE,
        lambda: _storage_input(pattern_id=_OTHER_ID),
        _store_deps(seed={"version": 3}),
    ),
    (
        "store-no-metadata-no-correlation",
        STORE,
        lambda: _storage_input(
            correlation_id=None, metadata=ModelPatternStorageMetadata()
        ),
        _store_deps(),
    ),
    (
        "store-low-confidence-rejected",
        STORE,
        _low_confidence_input,
        _store_deps(),
    ),
    (
        "store-blank-signature-and-domain-rejected",
        STORE,
        lambda: _storage_input(signature="  ", domain="\t"),
        _store_deps(),
    ),
    (
        "store-check-exists-raises",
        STORE,
        _storage_input,
        _store_deps(fail_on="check_exists_by_id"),
    ),
    (
        "store-insert-raises",
        STORE,
        _storage_input,
        _store_deps(fail_on="store_pattern"),
    ),
    # --- HandlerPromotePattern -----------------------------------------------
    (
        "promote-candidate-to-provisional",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL, metrics_snapshot=_METRICS),
        _state_deps({_PATTERN_ID: _CANDIDATE}),
    ),
    (
        "promote-provisional-to-validated-full-context",
        PROMOTE,
        lambda: _promote_request(
            _VALIDATED,
            metrics_snapshot=_METRICS,
            actor="verifier",
            correlation_id=_CORRELATION_ID,
            domain=_DOMAIN,
            signature_hash=_HASH,
            metadata={"ticket": "OMN-1"},
        ),
        _state_deps({_PATTERN_ID: _PROVISIONAL}),
    ),
    (
        "promote-without-metrics-default-actor",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL),
        _state_deps({_PATTERN_ID: _CANDIDATE}),
    ),
    (
        "promote-pattern-not-found",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL),
        _state_deps({}),
    ),
    (
        "promote-skip-state-invalid",
        PROMOTE,
        lambda: _promote_request(_VALIDATED),
        _state_deps({_PATTERN_ID: _CANDIDATE}),
    ),
    (
        "promote-from-terminal-invalid",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL),
        _state_deps({_PATTERN_ID: _VALIDATED}),
    ),
    (
        "promote-same-state-invalid",
        PROMOTE,
        lambda: _promote_request(_CANDIDATE),
        _state_deps({_PATTERN_ID: _CANDIDATE}),
    ),
    (
        "promote-update-state-raises",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL),
        _state_deps({_PATTERN_ID: _CANDIDATE}, fail_on="update_state"),
    ),
    (
        "promote-record-transition-raises",
        PROMOTE,
        lambda: _promote_request(_PROVISIONAL),
        _state_deps({_PATTERN_ID: _CANDIDATE}, fail_on="record_transition"),
    ),
]


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(json.dumps(_plain(request_builder()), default=str)),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _fake_state(deps: dict[str, Any]) -> dict[str, Any]:
    """Return the comparable end state of whichever fake the case injected."""
    store = deps.get("pattern_store")
    if store is not None:
        return {
            "patterns": store.patterns,
            "idempotency_map": store.idempotency_map,
            "versions": store._version_tracker,
            "atomic": store._atomic_transitions_count,
        }
    manager = deps["state_manager"]
    # ``ModelStateTransition.id`` is a per-instance random default bound at class
    # definition (``default_factory=uuid4``), so it is the one masked field; the
    # idempotency ``event_id`` comes from the patched ``uuid4`` and is compared.
    return {
        "states": manager.states,
        "transitions": [t.model_dump(exclude={"id"}) for t in manager.transitions],
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], Any],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper returns (or raises) exactly what the preserved function does."""
    wrapper_cls = getattr(
        importlib.import_module(_WRAPPER_MODULES[class_name]), class_name, None
    )
    assert wrapper_cls is not None, "contract-bound handler class is required"

    counter = {"n": 0}

    def fake_uuid4() -> UUID:
        counter["n"] += 1
        return UUID(f"00000000-0000-0000-0000-{0xE00 + counter['n']:012d}")

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, *_args: Any, **_kwargs: Any) -> datetime:
            return _FIXED_TIME

    for module_name in (STORE_MODULE, PROMOTE_MODULE):
        monkeypatch.setattr(
            importlib.import_module(module_name), "datetime", _FixedDatetime
        )
    monkeypatch.setattr(importlib.import_module(PROMOTE_MODULE), "uuid4", fake_uuid4)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()
    preserved = _PRESERVED[class_name]

    async def run_preserved() -> Any:
        if class_name in _SPLAT_WRAPPERS:
            return await preserved(**request_b, **deps_b)
        return await preserved(request_b, **deps_b)

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    counter["n"] = 0
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    counter["n"] = 0
    try:
        function_result = await run_preserved()
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert _fake_state(deps_a) == _fake_state(deps_b)
    if case_id.endswith("-raises"):
        assert function_error is not None
