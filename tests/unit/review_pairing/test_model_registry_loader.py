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
from tests.fixtures.model_constants import MODEL_DEEPSEEK_R1, MODEL_QWEN3_14B

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_load_registry_returns_contract_with_expected_keys() -> None:
    contract = load_registry()

    assert contract.default_model_key == MODEL_DEEPSEEK_R1
    assert set(contract.local_model_keys) == {
        MODEL_DEEPSEEK_R1,
        "qwen3-review",
        "qwen3-review-b",
        "qwen3-coder",
        MODEL_QWEN3_14B,
        "qwen3-next",
    }
    assert contract.api_fallback_keys == ("codex",)
    assert set(contract.models.keys()) == {
        MODEL_DEEPSEEK_R1,
        "qwen3-review",
        "qwen3-review-b",
        "qwen3-coder",
        MODEL_QWEN3_14B,
        "qwen3-next",
        "codex",
        "glm-review",
    }


def test_glm_review_entry_pins_coding_plan_surface() -> None:
    """glm-review (OMN-17492) rides the z.ai GLM Coding Plan.

    Mirrors omnimarket's test_glm_coding_plan_endpoint_omn6790: the Coding
    Plan is served ONLY at /api/coding/paas/v4 -- the pay-as-you-go surface
    (/api/paas/v4) answers a Coding-Plan key with 429 code 1113, which reads
    as billing but means WRONG ENDPOINT (OMN-6790, rediscovered three times).
    This pin fails closed on any drift off the coding surface.
    """
    contract = load_registry()
    glm = contract.models["glm-review"]

    assert glm.default_url.startswith("https://api.z.ai/api/coding/paas/v4"), (
        "glm-review must target the z.ai Coding Plan surface "
        "/api/coding/paas/v4 (OMN-6790); the pay-as-you-go surface refuses "
        "Coding-Plan keys with 429 code 1113."
    )
    # COMPLETE chat-completions URL: call_model uses it verbatim instead of
    # appending /v1/chat/completions (which would 404 on z.ai).
    assert glm.default_url.endswith("/chat/completions")
    assert glm.api_model_id == "glm-5.3-flash"
    assert glm.api_key_env == "LLM_GLM_API_KEY"  # pragma: allowlist secret
    assert glm.kind == "code_review"
    # Cloud reviewer: never TCP-probed as a LAN endpoint, never part of the
    # local-reachability fallback -- its independence from the .201 GPU is
    # the point (OMN-16481).
    assert "glm-review" not in contract.local_model_keys
    assert "glm-review" not in contract.api_fallback_keys


def test_local_models_declare_no_api_key_env() -> None:
    """api_key_env is additive: every pre-OMN-17492 entry must be unaffected."""
    contract = load_registry()
    for key, config in contract.models.items():
        if key == "glm-review":
            continue
        assert config.api_key_env is None, (
            f"{key} unexpectedly declares api_key_env; only authenticated "
            "cloud reviewers set it."
        )


def test_load_registry_preserves_endpoint_config_fields() -> None:
    contract = load_registry()

    deepseek = contract.models[MODEL_DEEPSEEK_R1]
    assert deepseek.env_var == "LLM_DEEPSEEK_R1_URL"
    # OMN-16407 residual (2026-08-23): repointed 8001 -> 8000 after the RTX
    # 4090 this key targeted was physically removed for RMA; api_model_id
    # now matches the live-served SGLang id on :8000 (same endpoint
    # qwen3-review / qwen3-review-b use).
    assert deepseek.default_url == "http://192.168.86.201:8000"
    assert deepseek.kind == "reasoning"
    assert deepseek.timeout_seconds == 300.0
    assert deepseek.api_model_id == "qwen3.8"

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
