# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Compare typed reducer output with the actual pre-flip process handler."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from uuid import UUID

import pytest

from omniintelligence.nodes.node_intelligence_reducer.handlers import (
    handler_pattern_lifecycle as lifecycle,
)
from omniintelligence.nodes.node_intelligence_reducer.handlers import (
    handler_process as canonical,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)

BASE_REF = "688acb01"
CASES = {
    "promote_legacy": ("provisional", "validated", "promote", "handler"),
    "promote_direct": ("candidate", "validated", "promote_direct", "handler"),
    "deprecate_candidate": ("candidate", "deprecated", "deprecate", "handler"),
    "deprecate_legacy": ("provisional", "deprecated", "deprecate", "handler"),
    "deprecate_validated": ("validated", "deprecated", "deprecate", "handler"),
    "reenable": ("deprecated", "candidate", "manual_reenable", "admin"),
    "guard_failure": ("deprecated", "candidate", "manual_reenable", "handler"),
    "invalid_trigger": ("candidate", "validated", "unknown", "handler"),
    "invalid_transition": ("candidate", "validated", "promote", "handler"),
    "state_mismatch": ("candidate", "deprecated", "promote_direct", "handler"),
    "invalid_pattern_id": ("candidate", "validated", "promote_direct", "handler"),
}


def _legacy_handler() -> ModuleType:
    root = Path(__file__).resolve().parents[3]
    relative = "src/omniintelligence/nodes/node_intelligence_reducer/handlers/handler_process.py"
    source = subprocess.run(
        ["git", "show", f"{BASE_REF}:{relative}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    module = ModuleType("legacy_reducer_process")
    exec(compile(source, "<legacy_reducer_process>", "exec"), module.__dict__)
    return module


def replay_input(case: str) -> ModelReducerInputPatternLifecycle:
    """Build the deterministic request used for parity and coverage recording."""
    from_status, to_status, trigger, actor_type = CASES[case]
    pattern_id = (
        "invalid"
        if case == "invalid_pattern_id"
        else "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    return ModelReducerInputPatternLifecycle.model_validate(
        {
            "fsm_type": "PATTERN_LIFECYCLE",
            "entity_id": pattern_id,
            "action": trigger,
            "correlation_id": "12345678-1234-5678-1234-567812345678",
            "request_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "payload": {
                "pattern_id": pattern_id,
                "from_status": from_status,
                "to_status": to_status,
                "trigger": trigger,
                "actor_type": actor_type,
                "actor": "parity-test",
                "reason": "handler conversion parity",
            },
        }
    )


@pytest.mark.unit
@pytest.mark.parametrize("case", CASES)
def test_canonical_dispatch_matches_legacy(case: str) -> None:
    """Freeze only clocks and generated IDs; compare every output field."""
    handler_type = getattr(canonical, "HandlerPatternLifecycleProcess", None)
    assert handler_type is not None, "typed handler class must exist"
    legacy = _legacy_handler()
    request = replay_input(case)
    transition = partial(
        lifecycle.handle_pattern_lifecycle_transition,
        transition_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    operation_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    intent_type = partial(canonical.ModelIntent, intent_id=operation_id)
    output_type = partial(
        canonical.ModelReducerOutput, timestamp=datetime(2026, 1, 1, tzinfo=UTC)
    )
    with (
        patch.object(canonical.time, "perf_counter", return_value=100.0),
        patch.object(canonical, "uuid4", return_value=operation_id),
        patch.object(legacy, "uuid4", return_value=operation_id),
        patch.object(canonical, "handle_pattern_lifecycle_transition", transition),
        patch.object(legacy, "handle_pattern_lifecycle_transition", transition),
        patch.object(canonical, "ModelIntent", intent_type),
        patch.object(legacy, "ModelIntent", intent_type),
        patch.object(canonical, "ModelReducerOutput", output_type),
        patch.object(legacy, "ModelReducerOutput", output_type),
    ):
        expected = legacy.handle_pattern_lifecycle_process(request)
        actual = handler_type().handle(request)

    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
