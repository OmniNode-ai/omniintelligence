# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The runtime's bind address and listener ports come from a contract (OMN-21680).

``runtime/runtime_bindings.yaml`` declares them; ``ModelRuntimeBindings`` is the one
reader. The runtime config, the stub launcher and the decision_store entrypoint hold
no literal for any of them, and a file that omits a field, or names an unknown one,
fails to load rather than falling back to a value in code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from omniintelligence.models.runtime_bindings import (
    ModelRuntimeBindings,
    ModelRuntimeBindingsLoadError,
    runtime_bindings,
)
from omniintelligence.runtime.model_intelligence_runtime_config import (
    ModelIntelligenceRuntimeConfig,
)

pytestmark = pytest.mark.unit

_SHIPPED = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "omniintelligence"
    / "runtime"
    / "runtime_bindings.yaml"
)


def _shipped_document() -> dict[str, Any]:
    return yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))


def _write(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "runtime_bindings.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_shipped_file_declares_every_field() -> None:
    bindings = runtime_bindings()
    assert set(_shipped_document()) == set(ModelRuntimeBindings.model_fields)
    assert bindings.bind_host
    assert (
        len(
            {
                bindings.runtime_health_port,
                bindings.runtime_metrics_port,
                bindings.stub_health_port,
                bindings.decision_store_health_port,
            }
        )
        == 4
    )


@pytest.mark.parametrize("missing", sorted(_shipped_document()))
def test_a_file_missing_one_field_fails_to_load(tmp_path: Path, missing: str) -> None:
    document = _shipped_document()
    del document[missing]
    with pytest.raises(ModelRuntimeBindingsLoadError, match=missing):
        ModelRuntimeBindings.load(_write(tmp_path, document))


def test_a_file_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["surprise"] = 1
    with pytest.raises(ModelRuntimeBindingsLoadError, match="surprise"):
        ModelRuntimeBindings.load(_write(tmp_path, document))


def test_a_port_outside_the_valid_range_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["stub_health_port"] = 70000
    with pytest.raises(ModelRuntimeBindingsLoadError, match="stub_health_port"):
        ModelRuntimeBindings.load(_write(tmp_path, document))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelRuntimeBindingsLoadError, match="not found"):
        ModelRuntimeBindings.load(tmp_path / "absent.yaml")


def test_runtime_config_ports_default_to_the_contract_values() -> None:
    bindings = runtime_bindings()
    config = ModelIntelligenceRuntimeConfig.default_development()
    assert config.health_check_port == bindings.runtime_health_port
    assert config.metrics_port == bindings.runtime_metrics_port
