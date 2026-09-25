# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""gpt-oss-120b is registered as a reviewer that is a different model.

Operator ruling of 2026-09-25 (ledger RULING, OMN-17492): hostile review uses
local models, gpt-oss-120b on the Mac Studio plus the .201 models. Before this,
the only local review keys (``qwen3-review`` and the since-deleted aliases
``qwen3-review-b`` and ``deepseek-r1``) all resolved to ONE endpoint,
``.201:8000``, which serves one model, so every two-model "agreement" was that
model agreeing with itself.

These tests pin three things:

* ``gpt-oss-review`` exists, is local, keyless and ``served`` (the id is read
  from the endpoint, never declared, per OMN-18623).
* Its endpoint is not the endpoint any existing local key uses, so it can
  never be the same model under a second name.
* ``reasoning_effort`` is a declarative per-model field that reaches the wire
  inside ``chat_template_kwargs``. It matters for this model: measured on
  2026-09-25 against ``.200:8130``, effort ``high`` spent all 4096 completion
  tokens on reasoning and returned an empty answer on a 98-line diff
  (omnimarket#2871), while ``low`` and ``medium`` answered.

Reference: OMN-17492, OMN-18479, OMN-18623.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from omniintelligence.review_pairing.model_registry_loader import load_registry
from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
)

_KEY = "gpt-oss-review"


def _host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "", parsed.port or 80


@pytest.mark.unit
class TestGptOssReviewerRegistered:
    def test_key_is_registered_as_a_local_served_code_reviewer(self) -> None:
        registry = load_registry()
        assert _KEY in registry.models
        entry = registry.models[_KEY]
        assert entry.kind == "code_review"
        assert entry.model_id_source == "served"
        assert entry.api_model_id == ""
        assert _KEY in registry.local_model_keys
        assert entry.env_var == "LLM_GPT_OSS_REVIEW_URL"

    def test_endpoint_is_the_mac_studio_llama_server(self) -> None:
        entry = load_registry().models[_KEY]
        assert _host_port(entry.default_url) == (
            "192.168.86.200",
            8130,
        )  # onex-allow-internal-ip

    def test_endpoint_differs_from_every_other_local_review_key(self) -> None:
        """A second name for an endpoint already registered is not a second
        reviewer. Positive control: the comparison detects a shared endpoint
        when one is present."""
        registry = load_registry()
        mine = _host_port(registry.models[_KEY].default_url)
        others = {
            key: _host_port(registry.models[key].default_url)
            for key in registry.local_model_keys
            if key != _KEY and registry.models[key].default_url
        }
        assert others, "no other local key with an endpoint to compare against"
        assert mine not in set(others.values())
        # Positive control: the same membership test finds an endpoint that
        # IS registered under another key (qwen3-review's own).
        assert _host_port(registry.models["qwen3-review"].default_url) in set(
            others.values()
        )

    def test_reasoning_effort_is_declared_and_bounded(self) -> None:
        entry = load_registry().models[_KEY]
        assert entry.reasoning_effort in ("low", "medium")


@pytest.mark.unit
class TestReasoningEffortField:
    def _base(self, **kw: object) -> dict[str, object]:
        data: dict[str, object] = {
            "env_var": "X_URL",
            "default_url": "http://h:1",
            "kind": "code_review",
            "timeout_seconds": 10.0,
        }
        data.update(kw)
        return data

    def test_defaults_to_none(self) -> None:
        assert ModelEndpointConfig.model_validate(self._base()).reasoning_effort is None

    @pytest.mark.parametrize("effort", ["low", "medium", "high"])
    def test_accepts_the_three_levels(self, effort: str) -> None:
        cfg = ModelEndpointConfig.model_validate(self._base(reasoning_effort=effort))
        assert cfg.reasoning_effort == effort

    def test_refuses_an_unknown_level(self) -> None:
        with pytest.raises(ValidationError):
            ModelEndpointConfig.model_validate(self._base(reasoning_effort="max"))


@pytest.mark.unit
class TestCallModelSendsReasoningEffort:
    @pytest.mark.asyncio
    async def test_gpt_oss_request_carries_effort_in_chat_template_kwargs(
        self,
    ) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        expected = load_registry().models[_KEY].reasoning_effort
        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_GPT_OSS_REVIEW_URL": "http://x:1",
            },
            clear=False,
        ):
            with (
                patch(
                    "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
                ) as handler_cls,
                patch(
                    "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
                    return_value="gpt-oss-120b",
                ),
            ):
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model("sys", "usr", model_key=_KEY)

        request = handler_inst.handle.call_args[0][0]
        assert request.extra_body == {
            "chat_template_kwargs": {
                "enable_thinking": False,
                "reasoning_effort": expected,
            }
        }
        assert request.model == "gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_entry_without_effort_sends_no_effort_key(self) -> None:
        """Positive control for the key above: qwen3-review declares no
        effort, so its kwargs are unchanged from OMN-14176."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_QWEN3_REVIEW_URL": "http://x:1",
            },
            clear=False,
        ):
            with (
                patch(
                    "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
                ) as handler_cls,
                patch(
                    "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
                    return_value="Qwen3.8-27B",
                ),
            ):
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-review"
                )

        request = handler_inst.handle.call_args[0][0]
        assert request.extra_body == {
            "chat_template_kwargs": {"enable_thinking": False}
        }


@pytest.mark.unit
class TestUnreachableModelIsNamedInTheResult:
    """A reviewer the reachability probe drops is named in the emitted result.

    Before OMN-17492 a local key whose TCP probe failed was removed from the
    roster and never appeared in the JSON: ``models_attempted`` listed only the
    survivors, so a run that lost the Mac Studio reviewer read exactly like a
    run that never asked for it. The workflows render their summary from this
    JSON, so the absence has to be in it.
    """

    def _run(self, tmp_path: Path, skipped: list[str]) -> dict[str, object]:
        import json

        from omniintelligence.review_pairing.cli_review import main
        from omniintelligence.review_pairing.models_external_review import (
            ModelExternalReviewResult,
        )
        from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
            PROMPT_VERSION,
        )

        plan = tmp_path / "plan.md"
        plan.write_text("# plan", encoding="utf-8")
        out = tmp_path / "out.json"
        roster = ["qwen3-review", "gpt-oss-review"]
        ran = [key for key in roster if key not in skipped]
        argv = ["--file", str(plan), "--output", str(out)]
        for key in roster:
            argv += ["--model", key]
        results = [
            ModelExternalReviewResult(
                model=key, prompt_version=PROMPT_VERSION, success=True
            )
            for key in ran
        ]
        with (
            patch(
                "omniintelligence.review_pairing.cli_review.select_models_with_fallback",
                return_value=(ran, skipped),
            ),
            patch(
                "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
                new_callable=AsyncMock,
                side_effect=results,
            ),
        ):
            code = main(argv)
        payload = json.loads(out.read_text(encoding="utf-8"))
        payload["_exit"] = code
        return payload

    def test_skipped_model_is_attempted_failed_and_explained(
        self, tmp_path: Path
    ) -> None:
        payload = self._run(tmp_path, ["gpt-oss-review"])
        assert "gpt-oss-review" in payload["models_attempted"]
        assert payload["models_failed"] == ["gpt-oss-review"]
        entry = [r for r in payload["results"] if r["model"] == "gpt-oss-review"]
        assert len(entry) == 1
        assert entry[0]["success"] is False
        assert "unreachable" in entry[0]["error"]
        # One reviewer left is no quorum: the run fails closed
        # (omnibase_infra#4119), never a degraded single-model pass.
        assert payload["_exit"] == 2
        assert payload["quorum"]["verdict"] == "degraded_quorum"
        assert payload["quorum"]["models_succeeded"] == ["qwen3-review"]

    def test_nothing_skipped_adds_no_failed_entry(self, tmp_path: Path) -> None:
        """Positive control: the entry above comes from the skip, not always."""
        payload = self._run(tmp_path, [])
        assert payload["models_failed"] == []
        assert [r["model"] for r in payload["results"]] == [
            "qwen3-review",
            "gpt-oss-review",
        ]
        assert payload["_exit"] == 0
        assert payload["quorum"]["verdict"] == "passed"
