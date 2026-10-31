# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Runtime timeout, poll and heartbeat budgets come from a contract (OMN-21623).

``runtime/runtime_timeouts.yaml`` declares them; ``ModelRuntimeTimeouts`` is the one
reader. The consumers hold no literal for any of them, and a file that omits a field,
or names an unknown one, fails to load rather than falling back to a value in code.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from omniintelligence.models.runtime_timeouts import (
    ModelRuntimeTimeouts,
    ModelRuntimeTimeoutsLoadError,
    runtime_timeouts,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_navigation_retrieve_input import (
    ModelNavigationRetrieveInput,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers import (
    handler_orchestrate,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
    handler_pattern_matching,
)
from omniintelligence.nodes.node_watchdog_effect.models.model_watchdog_config import (
    ModelWatchdogConfig,
)
from omniintelligence.runtime import dispatch_handler_pattern_learning

pytestmark = pytest.mark.unit

_SHIPPED = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "omniintelligence"
    / "runtime"
    / "runtime_timeouts.yaml"
)


def _shipped_document() -> dict[str, float]:
    return yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))


def _write(tmp_path: Path, document: dict[str, float]) -> Path:
    path = tmp_path / "runtime_timeouts.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_shipped_file_declares_every_field_with_a_positive_budget() -> None:
    timeouts = runtime_timeouts()
    assert set(_shipped_document()) == set(ModelRuntimeTimeouts.model_fields)
    for name in ModelRuntimeTimeouts.model_fields:
        assert getattr(timeouts, name) > 0, name


@pytest.mark.parametrize("missing", sorted(_shipped_document()))
def test_a_file_missing_one_field_fails_to_load(tmp_path: Path, missing: str) -> None:
    document = _shipped_document()
    del document[missing]
    with pytest.raises(ModelRuntimeTimeoutsLoadError, match=missing):
        ModelRuntimeTimeouts.load(_write(tmp_path, document))


def test_a_file_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["surprise"] = 1.0
    with pytest.raises(ModelRuntimeTimeoutsLoadError, match="surprise"):
        ModelRuntimeTimeouts.load(_write(tmp_path, document))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelRuntimeTimeoutsLoadError, match="not found"):
        ModelRuntimeTimeouts.load(tmp_path / "absent.yaml")


def test_a_non_positive_budget_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["watchdog_poll_s"] = 0
    with pytest.raises(ModelRuntimeTimeoutsLoadError, match="watchdog_poll_s"):
        ModelRuntimeTimeouts.load(_write(tmp_path, document))


def test_the_node_defaults_read_their_budgets_from_the_contract() -> None:
    timeouts = runtime_timeouts()
    navigation = ModelNavigationRetrieveInput.model_fields["timeout_seconds"]
    assert navigation.default == timeouts.navigation_retrieve_s
    assert (
        timeouts.pattern_assembly_workflow_s
        == handler_orchestrate.DEFAULT_TIMEOUT_SECONDS
    )
    regex = inspect.signature(handler_pattern_matching._timeout_protected_regex_search)
    assert regex.parameters["timeout"].default == timeouts.regex_match_s
    watchdog = ModelWatchdogConfig.model_fields["polling_interval_seconds"]
    assert watchdog.default == timeouts.watchdog_poll_s


def test_the_runtime_modules_read_their_budgets_from_the_contract() -> None:
    timeouts = runtime_timeouts()
    assert (
        timeouts.session_query_s
        == dispatch_handler_pattern_learning._SESSION_QUERY_TIMEOUT_SECONDS
    )
