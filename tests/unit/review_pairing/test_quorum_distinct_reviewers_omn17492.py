# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The quorum counts reviewers by distinct endpoint and model, not by key.

Before this change ``evaluate_quorum`` counted registry KEYS. ``qwen3-review``,
``qwen3-review-b`` and ``deepseek-r1`` all resolved to one endpoint serving one
model, so a roster of two of them met the two-model quorum with one model
agreeing with itself. On the OMN-17492 eval (2026-09-25) that pair agreed on a
critical finding in 2 of 8 runs, and both agreed findings were false.

A reviewer's identity is now its resolved endpoint plus the model that
endpoint is asked for: the declared ``api_model_id`` for a multi-model
endpoint, or ``served`` for a single-model endpoint whose id is resolved at
call time (OMN-18623), where the endpoint alone names the model. Two keys with
one identity count once, for the quorum and for agreement.

The two aliases are deleted from the registry, and so is ``glm-review`` with
the authenticated cloud path it used: private diffs go only to lab models
(operator, 2026-09-25).

Every zero here has a positive control beside it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.model_registry_loader import load_registry
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelEndpointConfig,
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelReviewQuorumPolicy,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from omniintelligence.review_pairing.quorum import evaluate_quorum
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity

pytestmark = pytest.mark.unit

_POLICY = ModelReviewQuorumPolicy()
_QWEN = "http://192.168.86.201:8000"  # onex-allow-internal-ip
_GPT_OSS = "http://192.168.86.200:8130"  # onex-allow-internal-ip
_QWEN_ID = f"{_QWEN}#served"
_GPT_OSS_ID = f"{_GPT_OSS}#served"


def _finding(model: str) -> ModelReviewFindingObserved:
    return ModelReviewFindingObserved(
        finding_id=uuid4(),
        repo="OmniNode-ai/omnibase_infra",
        pr_id=4124,
        rule_id=f"ai-reviewer:{model}:security",
        severity=EnumFindingSeverity.CRITICAL,
        file_path="src/app.py:120",
        line_start=1,
        line_end=None,
        tool_name=f"ai-reviewer:{model}",
        tool_version=PROMPT_VERSION,
        normalized_message="unvalidated input reaches the query builder",
        raw_message="unvalidated input reaches the query builder",
        commit_sha_observed="d150280",
        observed_at=datetime(2026, 9, 25, 19, 0, tzinfo=UTC),
    )


def _result(
    model: str, identity: str | None, *, raises: bool = True
) -> ModelExternalReviewResult:
    findings = [_finding(model)] if raises else []
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=findings,
        result_count=len(findings),
        reviewer_identity=identity,
    )


def _multi(*results: ModelExternalReviewResult) -> ModelMultiReviewResult:
    return ModelMultiReviewResult(
        models_attempted=[r.model for r in results],
        models_succeeded=[r.model for r in results],
        results=list(results),
        total_findings=sum(r.result_count for r in results),
    )


def _config(url: str, **extra: object) -> ModelEndpointConfig:
    fields: dict[str, object] = {
        "env_var": "LLM_TEST_REVIEW_URL",
        "default_url": url,
        "kind": "code_review",
        "timeout_seconds": 60.0,
        "model_id_source": "served",
    }
    fields.update(extra)
    return ModelEndpointConfig(**fields)  # type: ignore[arg-type]


class TestQuorumCountsDistinctReviewers:
    def test_two_names_for_one_model_are_no_quorum(self) -> None:
        summary = evaluate_quorum(
            _multi(_result("qwen3-review", _QWEN_ID), _result("alias", _QWEN_ID)),
            _POLICY,
        )
        assert summary.quorum_met is False
        assert summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM
        assert summary.distinct_reviewers_succeeded == (_QWEN_ID,)
        assert summary.blocking_count == 0

    def test_two_different_models_that_agree_block(self) -> None:
        """Positive control: the same finding from two identities blocks."""
        summary = evaluate_quorum(
            _multi(
                _result("qwen3-review", _QWEN_ID),
                _result("gpt-oss-review", _GPT_OSS_ID),
            ),
            _POLICY,
        )
        assert summary.quorum_met is True
        assert summary.verdict is EnumQuorumVerdict.BLOCKED
        assert summary.distinct_reviewers_succeeded == (_QWEN_ID, _GPT_OSS_ID)
        assert summary.blocking_findings[0].agreement_count == 2

    def test_an_alias_agreeing_with_itself_does_not_block(self) -> None:
        """Quorum met by a third reviewer; the finding only one model raised."""
        summary = evaluate_quorum(
            _multi(
                _result("qwen3-review", _QWEN_ID),
                _result("alias", _QWEN_ID),
                _result("gpt-oss-review", _GPT_OSS_ID, raises=False),
            ),
            _POLICY,
        )
        assert summary.quorum_met is True
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert summary.blocking_count == 0
        warning = summary.warning_findings[0]
        assert warning.agreement_count == 1
        assert warning.agreeing_models == ("qwen3-review", "alias")

    def test_a_result_without_identity_counts_by_its_key(self) -> None:
        summary = evaluate_quorum(
            _multi(_result("a", None), _result("b", None)), _POLICY
        )
        assert summary.quorum_met is True
        assert summary.distinct_reviewers_succeeded == ("key:a", "key:b")


class TestReviewerIdentity:
    def test_same_endpoint_is_one_served_reviewer(self) -> None:
        env: dict[str, str] = {}
        assert reviewer_identity("a", _config(_QWEN), env) == reviewer_identity(
            "b", _config(_QWEN + "/v1/"), env
        )

    def test_different_endpoint_is_a_different_reviewer(self) -> None:
        env: dict[str, str] = {}
        assert reviewer_identity("a", _config(_QWEN), env) != reviewer_identity(
            "b", _config(_GPT_OSS), env
        )

    def test_default_port_is_explicit(self) -> None:
        env: dict[str, str] = {}
        assert reviewer_identity(
            "a", _config("http://lab.example"), env
        ) == reviewer_identity("b", _config("http://lab.example:80"), env)

    def test_env_override_moves_the_identity(self) -> None:
        config = _config(_QWEN)
        moved = reviewer_identity("a", config, {"LLM_TEST_REVIEW_URL": _GPT_OSS})
        assert moved == _GPT_OSS_ID
        assert reviewer_identity("a", config, {}) == _QWEN_ID

    def test_declared_ids_on_one_endpoint_are_different_reviewers(self) -> None:
        env: dict[str, str] = {}
        one = _config(
            "https://cloud.example/v1/chat/completions",
            model_id_source="declared",
            api_model_id="model-a",
        )
        two = _config(
            "https://cloud.example/v1/chat/completions",
            model_id_source="declared",
            api_model_id="model-b",
        )
        assert reviewer_identity("a", one, env) != reviewer_identity("b", two, env)
        assert (
            reviewer_identity("a", one, env) == "https://cloud.example:443#id=model-a"
        )

    def test_a_declared_id_spelled_served_is_not_a_served_reviewer(self) -> None:
        """Found by the live lab review of this change (both lab models): the
        model part of a served entry and of a declared id must not share a
        namespace, or a declared id spelled ``served`` collides with it."""
        env: dict[str, str] = {}
        declared = _config(_QWEN, model_id_source="declared", api_model_id="served")
        assert reviewer_identity("a", declared, env) != reviewer_identity(
            "b", _config(_QWEN), env
        )

    def test_unknown_or_urlless_key_is_its_own_reviewer(self) -> None:
        assert reviewer_identity("codex", None, {}) == "key:codex"
        assert reviewer_identity("x", _config(""), {}) == "key:x"


class TestRegistryHasNoAliases:
    @pytest.mark.parametrize("key", ["qwen3-review-b", "deepseek-r1", "glm-review"])
    def test_alias_and_cloud_reviewer_are_deleted(self, key: str) -> None:
        registry = load_registry()
        assert key not in registry.models
        assert key not in registry.local_model_keys

    def test_default_key_is_a_lab_reviewer(self) -> None:
        assert load_registry().default_model_key == "qwen3-review"

    def test_the_lab_pair_is_two_reviewers(self) -> None:
        """Positive control for the uniqueness test below."""
        registry = load_registry()
        pair = {
            reviewer_identity(k, registry.models[k], {})
            for k in ("qwen3-review", "gpt-oss-review")
        }
        assert pair == {_QWEN_ID, _GPT_OSS_ID}

    def test_no_two_registry_keys_name_one_reviewer(self) -> None:
        registry = load_registry()
        seen: dict[str, str] = {}
        for key, config in registry.models.items():
            identity = reviewer_identity(key, config, {})
            assert identity not in seen, (
                f"{key} and {seen.get(identity)} are one reviewer ({identity})"
            )
            seen[identity] = key


class TestNoCloudReviewerCanBeRegistered:
    """The authenticated cloud path is deleted with glm-review.

    A registry entry that asks for a Bearer key (``api_key_env``) is refused
    at load, rather than silently ignored and sent to the cloud unkeyed.
    """

    def test_an_entry_with_a_key_env_is_refused(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _config(
                "https://cloud.example/v1/chat/completions",
                api_key_env="SOME_KEY_ENV",  # pragma: allowlist secret
            )

    def test_an_unknown_field_is_refused(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _config(_QWEN, not_a_field=True)

    def test_a_lab_entry_is_accepted(self) -> None:
        """Positive control: the same helper builds a valid entry."""
        assert _config(_QWEN).default_url == _QWEN


class TestCliStampsIdentity:
    def test_run_review_records_each_results_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        monkeypatch.delenv("LLM_QWEN3_REVIEW_URL", raising=False)
        monkeypatch.delenv("LLM_GPT_OSS_REVIEW_URL", raising=False)

        from omniintelligence.review_pairing import cli_review

        async def fake(content: str, *, model: str, **_: object) -> object:
            return ModelExternalReviewResult(
                model=model, prompt_version=PROMPT_VERSION, success=True
            )

        with patch.object(
            cli_review, "llm_async_parse_raw", AsyncMock(side_effect=fake)
        ):
            result = asyncio.run(
                cli_review.run_review(
                    "diff", ["qwen3-review", "gpt-oss-review"], review_type="pr"
                )
            )
        assert [r.reviewer_identity for r in result.results] == [
            _QWEN_ID,
            _GPT_OSS_ID,
        ]
