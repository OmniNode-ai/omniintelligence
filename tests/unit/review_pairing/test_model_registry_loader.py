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

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_load_registry_returns_contract_with_expected_keys() -> None:
    contract = load_registry()

    assert contract.default_model_key == "deepseek-r1"
    assert set(contract.local_model_keys) == {
        "deepseek-r1",
        "qwen3-coder",
        "qwen3-14b",
        "qwen3-next",
    }
    assert contract.api_fallback_keys == ("claude-api",)
    assert set(contract.models.keys()) == {
        "deepseek-r1",
        "qwen3-coder",
        "qwen3-14b",
        "qwen3-next",
        "claude-api",
    }


def test_load_registry_preserves_endpoint_config_fields() -> None:
    contract = load_registry()

    deepseek = contract.models["deepseek-r1"]
    assert deepseek.env_var == "LLM_DEEPSEEK_R1_URL"
    assert deepseek.default_url == "http://192.168.86.201:8001"
    assert deepseek.kind == "reasoning"
    assert deepseek.timeout_seconds == 300.0
    assert deepseek.api_model_id == "Corianas/DeepSeek-R1-Distill-Qwen-14B-AWQ"

    claude = contract.models["claude-api"]
    assert claude.env_var == "ANTHROPIC_API_BASE_URL"
    assert claude.default_url == "https://api.anthropic.com"
    assert claude.kind == "api_fallback"
    assert claude.timeout_seconds == 120.0
    assert claude.api_model_id == "claude-sonnet-4-6"


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
