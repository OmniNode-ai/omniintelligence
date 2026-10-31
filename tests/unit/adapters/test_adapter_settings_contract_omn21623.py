# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Client-adapter timeout budgets and chat endpoints come from a contract (OMN-21623).

``adapters/adapter_settings.yaml`` declares them; ``ModelAdapterSettings`` is the one
reader. The adapters hold no literal for any of them (the two plan-reviewer chat URLs included), and a file that omits a field,
or names an unknown one, fails to load rather than falling back to a value in code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from omniintelligence.adapters.eval_llm_client import EvalLLMClient
from omniintelligence.adapters.plan_reviewer_gemini_client import (
    ModelPlanReviewerGeminiConfig,
)
from omniintelligence.adapters.plan_reviewer_z_ai_client import (
    ModelPlanReviewerZAIConfig,
)
from omniintelligence.models.adapters import (
    ModelAdapterSettings,
    ModelAdapterSettingsLoadError,
    adapter_settings,
)

pytestmark = pytest.mark.unit

_SHIPPED = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "omniintelligence"
    / "adapters"
    / "adapter_settings.yaml"
)


def _shipped_document() -> dict[str, float | str]:
    return yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))


def _write(tmp_path: Path, document: dict[str, float | str]) -> Path:
    path = tmp_path / "adapter_settings.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_shipped_file_declares_every_field_with_a_positive_budget() -> None:
    settings = adapter_settings()
    assert set(_shipped_document()) == set(ModelAdapterSettings.model_fields)
    for name, field in ModelAdapterSettings.model_fields.items():
        if field.annotation is float:
            assert getattr(settings, name) > 0, name
        else:
            assert getattr(settings, name), name


@pytest.mark.parametrize("missing", sorted(_shipped_document()))
def test_a_file_missing_one_field_fails_to_load(tmp_path: Path, missing: str) -> None:
    document = _shipped_document()
    del document[missing]
    with pytest.raises(ModelAdapterSettingsLoadError, match=missing):
        ModelAdapterSettings.load(_write(tmp_path, document))


def test_a_file_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["surprise"] = 1.0
    with pytest.raises(ModelAdapterSettingsLoadError, match="surprise"):
        ModelAdapterSettings.load(_write(tmp_path, document))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelAdapterSettingsLoadError, match="not found"):
        ModelAdapterSettings.load(tmp_path / "absent.yaml")


def test_a_non_positive_timeout_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["http_timeout_s"] = 0
    with pytest.raises(ModelAdapterSettingsLoadError, match="http_timeout_s"):
        ModelAdapterSettings.load(_write(tmp_path, document))


def test_the_plan_reviewer_configs_default_their_timeout_from_the_contract() -> None:
    settings = adapter_settings()
    assert (
        ModelPlanReviewerGeminiConfig(api_key="k").timeout_seconds
        == settings.gemini_timeout_s
    )
    assert (
        ModelPlanReviewerZAIConfig(api_key="k").timeout_seconds
        == settings.zai_timeout_s
    )


def test_the_plan_reviewer_configs_default_their_chat_url_from_the_contract() -> None:
    settings = adapter_settings()
    assert (
        ModelPlanReviewerGeminiConfig(api_key="k").chat_url == settings.gemini_chat_url
    )
    assert ModelPlanReviewerZAIConfig(api_key="k").chat_url == settings.zai_chat_url


def test_a_caller_supplied_chat_url_overrides_the_contract_default() -> None:
    assert (
        ModelPlanReviewerZAIConfig(
            api_key="k", chat_url="http://injected/chat"
        ).chat_url
        == "http://injected/chat"
    )


def test_an_empty_chat_url_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["zai_chat_url"] = ""
    with pytest.raises(ModelAdapterSettingsLoadError, match="zai_chat_url"):
        ModelAdapterSettings.load(_write(tmp_path, document))


def test_a_caller_supplied_timeout_overrides_the_contract_default() -> None:
    assert (
        ModelPlanReviewerZAIConfig(api_key="k", timeout_seconds=7.0).timeout_seconds
        == 7.0
    )
    assert (
        EvalLLMClient(
            "http://gen", "http://judge", timeout_seconds=3.5
        )._timeout_seconds
        == 3.5
    )


def test_the_eval_client_timeout_defaults_from_the_contract() -> None:
    client = EvalLLMClient("http://gen", "http://judge")
    assert client._timeout_seconds == adapter_settings().eval_timeout_s
