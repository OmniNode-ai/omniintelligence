# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the hostile-reviewer model registry loader (OMN-7213)."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.review_pairing.model_registry_loader import (
    ModelRegistryLoadError,
    load_registry,
)
from tests.fixtures.model_constants import MODEL_QWEN3_14B

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_load_registry_returns_contract_with_expected_keys() -> None:
    contract = load_registry()

    # OMN-17492 (2026-09-25): deepseek-r1 and qwen3-review-b were further
    # names for the one model behind qwen3-review, and glm-review was a
    # third-party cloud reviewer. All three are deleted.
    assert contract.default_model_key == "qwen3-review"
    assert set(contract.local_model_keys) == {
        "qwen3-review",
        "gpt-oss-review",
        "qwen3-coder",
        MODEL_QWEN3_14B,
        "qwen3-next",
    }
    assert contract.api_fallback_keys == ("codex",)
    assert set(contract.models.keys()) == {
        "qwen3-review",
        "gpt-oss-review",
        "qwen3-coder",
        MODEL_QWEN3_14B,
        "qwen3-next",
        "codex",
    }


def test_load_registry_preserves_endpoint_config_fields() -> None:
    contract = load_registry()

    qwen = contract.models["qwen3-review"]
    assert qwen.env_var == "LLM_QWEN3_REVIEW_URL"
    assert qwen.default_url == "http://192.168.86.201:8000"  # onex-allow-internal-ip
    # OMN-18623 (2026-09-17): this entry declares NO model id at all.
    # Operator ruling 2026-09-17T19:54:09Z -- the reviewer's model must not be
    # a hardcoded literal. The id is resolved at call time from the endpoint's
    # /v1/models. Asserting EMPTINESS is the point: a value reappearing in this
    # field is the regression.
    assert qwen.api_model_id == ""
    assert qwen.model_id_source == "served"

    codex = contract.models["codex"]
    assert codex.env_var == "CODEX_BINARY"
    assert codex.default_url == ""
    assert codex.kind == "cli_fallback"
    assert codex.timeout_seconds == 180.0
    assert codex.api_model_id == "codex"


def test_adapter_module_level_constants_match_contract() -> None:
    """Adapter-level MODEL_REGISTRY must be derived from the YAML contract."""
    from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
        _API_FALLBACK_KEYS,
        _DEFAULT_MODEL_KEY,
        _LOCAL_MODEL_KEYS,
        MODEL_REGISTRY,
    )

    contract = load_registry()
    assert contract.default_model_key == _DEFAULT_MODEL_KEY
    assert frozenset(contract.local_model_keys) == _LOCAL_MODEL_KEYS
    assert tuple(contract.api_fallback_keys) == _API_FALLBACK_KEYS
    assert dict(contract.models) == MODEL_REGISTRY


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


def test_load_registry_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ModelRegistryLoadError, match="not found"):
        load_registry(missing)


def test_load_registry_rejects_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ModelRegistryLoadError, match="must be a mapping"):
        load_registry(path)


def test_load_registry_rejects_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text("::not: valid: yaml\n:\n  -bad", encoding="utf-8")
    with pytest.raises(ModelRegistryLoadError, match="not valid YAML"):
        load_registry(path)


def test_load_registry_rejects_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text(
        "default_model_key: only\nlocal_model_keys: []\napi_fallback_keys: []\n",
        # models: missing entirely
        encoding="utf-8",
    )
    with pytest.raises(ModelRegistryLoadError, match="failed validation"):
        load_registry(path)


def test_load_registry_rejects_endpoint_with_missing_field(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text(
        """
default_model_key: broken
local_model_keys: [broken]
api_fallback_keys: []
models:
  broken:
    env_var: FOO
    default_url: ""
    # kind missing
    timeout_seconds: 10.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelRegistryLoadError, match="failed validation"):
        load_registry(path)


def test_load_registry_rejects_dangling_default_key(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text(
        """
default_model_key: ghost
local_model_keys: []
api_fallback_keys: []
models:
  real:
    env_var: FOO
    default_url: ""
    kind: reasoning
    timeout_seconds: 10.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelRegistryLoadError, match="undefined model keys"):
        load_registry(path)


def test_load_registry_rejects_dangling_local_key(tmp_path: Path) -> None:
    path = tmp_path / "reg.yaml"
    path.write_text(
        """
default_model_key: real
local_model_keys: [ghost]
api_fallback_keys: []
models:
  real:
    env_var: FOO
    default_url: ""
    kind: reasoning
    timeout_seconds: 10.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelRegistryLoadError, match="undefined model keys"):
        load_registry(path)


@pytest.mark.unit
def test_local_201_8000_keys_declare_no_model_id() -> None:
    """OMN-18623: keys on the shared LAN endpoint must declare NO model id.

    SUPERSEDES ``test_local_201_8000_keys_share_one_served_model_id``
    (OMN-17786), which asserted the keys carried ONE SHARED literal. That guard
    could not have prevented this ticket: it proved the keys agreed with EACH
    OTHER, and all three agreed perfectly throughout the 2026-09-17 outage --
    on a model that no longer existed -- because the value it compared them
    against was written in the same commit as the pins it checked.

    The invariant is now stronger and simpler: there is no value to agree on.
    Drift is unrepresentable rather than merely detectable.
    """
    contract = load_registry()
    on_8000 = {
        key: cfg
        for key, cfg in contract.models.items()
        if cfg.default_url == "http://192.168.86.201:8000"  # onex-allow-internal-ip
    }

    assert set(on_8000) == {"qwen3-review"}, (
        f"unexpected key set on .201:8000: {sorted(on_8000)}"
    )
    for key, cfg in sorted(on_8000.items()):
        assert cfg.model_id_source == "served", (
            f"{key} must resolve its model id from the endpoint, got "
            f"model_id_source={cfg.model_id_source!r}"
        )
        assert cfg.api_model_id == "", (
            f"{key} declares api_model_id={cfg.api_model_id!r}. A literal here "
            "is the OMN-16407/OMN-17786/OMN-18623 defect returning."
        )
