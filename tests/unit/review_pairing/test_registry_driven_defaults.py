# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests proving cli_review default model comes from the registry contract.

Motivation: OMN-11936 — cli_review.py had `_DEFAULT_MODEL = "deepseek-r1"`
hardcoded at line 71. It must be read from the adapter's registry-derived
constant so changing model_registry.yaml changes the CLI default without
editing Python source.

TDD sequence: write failing tests first, then fix cli_review.py.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from omniintelligence.review_pairing.model_registry_loader import (
    ModelRegistryContract,
    load_registry,
)
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(default_key: str = "my-custom-model") -> ModelRegistryContract:
    """Build a minimal ModelRegistryContract for an arbitrary default key."""
    return ModelRegistryContract(
        default_model_key=default_key,
        local_model_keys=(default_key,),
        api_fallback_keys=(),
        models={
            default_key: ModelEndpointConfig(
                env_var="MY_LLM_URL",
                default_url="http://localhost:9999",
                kind="fast_review",
                timeout_seconds=30.0,
                api_model_id=default_key,
            )
        },
    )


# ---------------------------------------------------------------------------
# Contract integrity: registry YAML drives the default
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistryDrivenDefault:
    """The CLI default model must come from model_registry.yaml, not source code."""

    def test_load_registry_returns_contract_with_default_key(self) -> None:
        """load_registry() returns a contract whose default_model_key is set."""
        contract = load_registry()
        assert isinstance(contract.default_model_key, str)
        assert contract.default_model_key  # non-empty

    def test_default_model_key_exists_in_model_registry(self) -> None:
        """The default_model_key declared in the YAML is in the models dict."""
        contract = load_registry()
        assert contract.default_model_key in contract.models, (
            f"default_model_key '{contract.default_model_key}' not in models: "
            f"{sorted(contract.models.keys())}"
        )

    def test_cli_review_default_model_matches_adapter_registry_key(self) -> None:
        """cli_review._DEFAULT_MODEL must equal adapter._DEFAULT_MODEL_KEY.

        This test FAILS when cli_review.py has its own hardcoded string instead
        of deriving _DEFAULT_MODEL from the adapter's registry constant.
        The fix: in cli_review.py, replace:
            _DEFAULT_MODEL: str = "deepseek-r1"
        with:
            import omniintelligence.review_pairing.adapters.adapter_ai_reviewer as adapter
            _DEFAULT_MODEL = adapter._DEFAULT_MODEL_KEY
        """
        import omniintelligence.review_pairing.adapters.adapter_ai_reviewer as adapter_ai_reviewer
        import omniintelligence.review_pairing.cli_review as cli_review_mod

        # Force a fresh import so module-level constants are current
        importlib.reload(adapter_ai_reviewer)
        importlib.reload(cli_review_mod)

        assert (
            cli_review_mod._DEFAULT_MODEL == adapter_ai_reviewer._DEFAULT_MODEL_KEY
        ), (
            f"cli_review._DEFAULT_MODEL='{cli_review_mod._DEFAULT_MODEL}' does not match "
            f"adapter._DEFAULT_MODEL_KEY='{adapter_ai_reviewer._DEFAULT_MODEL_KEY}'. "
            "Fix: derive _DEFAULT_MODEL from the adapter's registry constant."
        )

    def test_cli_review_default_model_tracks_registry_yaml(self) -> None:
        """When registry YAML default_model_key changes, cli_review._DEFAULT_MODEL tracks it.

        This test uses a fresh custom registry YAML to prove that cli_review
        reads through the registry rather than having its own hardcoded value.
        """
        import tempfile

        import yaml as pyyaml

        custom_yaml = {
            "default_model_key": "sentinel-custom-model",
            "local_model_keys": ["sentinel-custom-model"],
            "api_fallback_keys": [],
            "models": {
                "sentinel-custom-model": {
                    "env_var": "SENTINEL_LLM_URL",
                    "default_url": "http://localhost:19999",
                    "kind": "fast_review",
                    "timeout_seconds": 30.0,
                    "api_model_id": "sentinel-custom-model",
                }
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            pyyaml.dump(custom_yaml, f)
            tmp_path = Path(f.name)

        try:
            # Reload adapter with custom registry
            with patch(
                "omniintelligence.review_pairing.model_registry_loader._REGISTRY_PATH",
                tmp_path,
            ):
                import omniintelligence.review_pairing.adapters.adapter_ai_reviewer as adapter

                importlib.reload(adapter)
                # After reload, adapter._DEFAULT_MODEL_KEY should be "sentinel-custom-model"
                # cli_review should pick it up if it derives its constant from the adapter
                import omniintelligence.review_pairing.cli_review as cli_review_mod

                importlib.reload(cli_review_mod)

                assert cli_review_mod._DEFAULT_MODEL == "sentinel-custom-model", (
                    f"After changing registry YAML default_model_key to "
                    f"'sentinel-custom-model', cli_review._DEFAULT_MODEL is still "
                    f"'{cli_review_mod._DEFAULT_MODEL}'. "
                    "cli_review.py must derive _DEFAULT_MODEL from the adapter registry."
                )
        finally:
            tmp_path.unlink(missing_ok=True)
            # Restore adapter to real registry
            import omniintelligence.review_pairing.adapters.adapter_ai_reviewer as adapter

            importlib.reload(adapter)
            import omniintelligence.review_pairing.cli_review as cli_review_mod

            importlib.reload(cli_review_mod)


# ---------------------------------------------------------------------------
# Registry integrity: LLM_CODER_FAST_URL entry has api_model_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistryModelNameResolution:
    """Model names for LLM calls must resolve via registry, not be hardcoded literals."""

    def test_registry_has_fast_review_model_for_coder_url(self) -> None:
        """The registry must include a model served at LLM_CODER_FAST_URL.

        node_transition_selector_effect uses LLM_CODER_FAST_URL. The model
        name sent in the payload should come from the registry entry for this
        env var, not be a hardcoded 'qwen3-14b' string.
        """
        contract = load_registry()
        coder_fast_models = [
            key
            for key, config in contract.models.items()
            if config.env_var == "LLM_CODER_FAST_URL"
        ]
        assert coder_fast_models, (
            "model_registry.yaml must have at least one model with "
            "env_var='LLM_CODER_FAST_URL' so node_transition_selector_effect "
            "can resolve the model name without hardcoding 'qwen3-14b'."
        )

    def test_coder_fast_model_has_api_model_id(self) -> None:
        """The LLM_CODER_FAST_URL registry entry must have a non-empty api_model_id.

        This id is what gets sent in the chat completion payload. If it were
        empty, the node would have to hardcode a model name.
        """
        contract = load_registry()
        for key, config in contract.models.items():
            if config.env_var == "LLM_CODER_FAST_URL":
                assert config.api_model_id, (
                    f"Registry entry '{key}' for LLM_CODER_FAST_URL has empty "
                    "api_model_id. The transition selector node needs this value "
                    "to avoid hardcoding 'qwen3-14b' in the payload."
                )

    def test_adapter_model_registry_api_model_ids_all_set(self) -> None:
        """Every model in MODEL_REGISTRY used for LLM calls must have api_model_id."""
        import omniintelligence.review_pairing.adapters.adapter_ai_reviewer as adapter_ai_reviewer

        for key, config in adapter_ai_reviewer.MODEL_REGISTRY.items():
            if config.kind == "api_fallback":
                continue  # Claude API uses its own model id path
            assert isinstance(config.api_model_id, str), (
                f"Model '{key}' (kind={config.kind}) has non-string api_model_id"
            )
