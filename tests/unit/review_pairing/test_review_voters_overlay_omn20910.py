# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The Hostile Reviewer's voters come from a contract overlay (OMN-20910).

Operator RULING 2026-10-10T18:17:37Z: review-voter models are declared in a
contract overlay, never in repository variables or workflow files. These tests
hold the three properties that ruling needs:

* loading -- a voter's endpoint resolves from the lab delegation overlay
  (``backend_id``) or from its own ``endpoint_url``, and its model selection,
  sampling and focus reach the per-call config unchanged;
* validation -- every malformed entry is refused at load time, and the error
  names the voter;
* failure -- a required voter that is unreachable or does not vote fails the
  run with exit 2 and its id on stderr; nothing is substituted for it.
"""

from __future__ import annotations

import asyncio
import json
import re
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from omniintelligence.nodes.node_review_voters_overlay_compute.handlers.handler_review_voters_overlay import (
    handle,
    probe_target_lines,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter_roster import (
    ModelReviewVoterRoster,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voters_overlay_request import (
    ModelReviewVotersOverlayRequest,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.cli_review import main, run_review
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelReviewQuorumPolicy,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from omniintelligence.review_pairing.quorum import evaluate_quorum
from omniintelligence.review_pairing.retry_budget import (
    main as retry_budget_main,
)
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity

_BIFROST = textwrap.dedent(
    """\
    schema_version: "bifrost_lane_overlay.v3"
    lane: dev
    locale: lab
    backends:
      - backend_id: lab-a
        endpoint_url: "http://voter-a.example:8000/v1/chat/completions"
        served_model_id: "Model-A"
      - backend_id: lab-b
        endpoint_url: "http://voter-b.example:8130/v1/chat/completions"
        served_model_id: "Model-B"
      - backend_id: lab-unbound
        endpoint_url: null
    """
)

_REVIEW_ENV_NAME = "REVIEW_ANTHROPIC_API_KEY"

_VOTERS = textwrap.dedent(
    """\
    schema_version: "review_voters_overlay.v1"
    backend_overlay: bifrost.yaml
    voters:
      - voter_id: first
        backend_id: lab-a
        required: true
        timeout_seconds: 120
        temperature: 0.3
        review_focus: "Correctness first."
      - voter_id: second
        backend_id: lab-b
        required: true
        timeout_seconds: 300
        max_retries: 1
        temperature: 0.7
        top_p: 0.8
        constrain_findings_schema: true
        review_focus: "Security first."
    """
)


def _write(tmp_path: Path, voters: str = _VOTERS, bifrost: str = _BIFROST) -> Path:
    (tmp_path / "bifrost.yaml").write_text(bifrost, encoding="utf-8")
    path = tmp_path / "voters.yaml"
    path.write_text(voters, encoding="utf-8")
    return path


def _with_second(tmp_path: Path, **fields: object) -> Path:
    """The default overlay with the second voter's fields replaced."""
    lines = [
        'schema_version: "review_voters_overlay.v1"',
        "backend_overlay: bifrost.yaml",
        *(
            ["provider_endpoints:", '  anthropic: "https://api.anthropic.com"']
            if fields.get("provider") == "anthropic"
            else []
        ),
        "voters:",
        "  - voter_id: first",
        "    backend_id: lab-a",
        "    required: true",
        "    timeout_seconds: 120",
        "  - voter_id: second",
    ]
    lines += [f"    {key}: {value}" for key, value in fields.items()]
    return _write(tmp_path, "\n".join(lines) + "\n")


def _success(model: str) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=[],
        result_count=0,
    )


def _failure(model: str, error: str) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model, prompt_version=PROMPT_VERSION, success=False, error=error
    )


def _refused(path: Path) -> ModelReviewVoterRoster:
    roster = load_review_voters(path)
    assert not roster.ok, "the overlay was expected to be refused"
    assert roster.voters == ()
    return roster


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    """register_review_voters mutates the adapter's registry; undo it."""
    registry = dict(adapter_ai_reviewer.MODEL_REGISTRY)
    local_keys = adapter_ai_reviewer._LOCAL_MODEL_KEYS
    yield
    adapter_ai_reviewer.MODEL_REGISTRY.clear()
    adapter_ai_reviewer.MODEL_REGISTRY.update(registry)
    adapter_ai_reviewer._LOCAL_MODEL_KEYS = local_keys


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoading:
    def test_anthropic_voter_without_endpoint(self, tmp_path: Path) -> None:
        roster = load_review_voters(
            _with_second(
                tmp_path,
                provider="anthropic",
                model="claude-sonnet-5-5",
                api_key_env=_REVIEW_ENV_NAME,
                required="true",
                timeout_seconds=60,
                max_retries=1,
            )
        )
        assert roster.ok, roster.error_message
        config = roster.endpoint_configs()["second"]
        assert config.provider == "anthropic"
        assert config.api_model_id == "claude-sonnet-5-5"
        assert config.api_key_env == _REVIEW_ENV_NAME
        assert config.model_id_source == "declared"
        assert config.timeout_seconds == 60
        assert config.max_retries == 1

    def test_changing_anthropic_model_is_an_overlay_only_swap(
        self, tmp_path: Path
    ) -> None:
        before = load_review_voters(_anthropic_overlay(tmp_path)).endpoint_configs()[
            "second"
        ]
        after = load_review_voters(
            _anthropic_overlay(tmp_path, model="another-sonnet")
        ).endpoint_configs()["second"]
        assert before.default_url == after.default_url
        assert before.api_model_id == "claude-sonnet-5-5"
        assert after.api_model_id == "another-sonnet"
        assert before.model_copy(update={"api_model_id": after.api_model_id}) == after

    def test_backend_voters_resolve_through_the_delegation_overlay(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_write(tmp_path))

        assert roster.voter_ids == ["first", "second"]
        assert roster.required_ids == frozenset({"first", "second"})
        first, second = roster.voters
        assert first.base_url == "http://voter-a.example:8000"
        assert second.base_url == "http://voter-b.example:8130"
        assert second.backend_served_model_id == "Model-B"

    def test_sampling_focus_and_model_reach_the_call_config(
        self, tmp_path: Path
    ) -> None:
        configs = load_review_voters(_write(tmp_path)).endpoint_configs()

        second = configs["second"]
        assert second.default_url == "http://voter-b.example:8130"
        assert second.model_id_source == "served"
        assert second.api_model_id == ""
        assert second.temperature == 0.7
        assert second.top_p == 0.8
        assert second.review_focus == "Security first."
        assert second.timeout_seconds == 300
        assert second.max_retries == 1
        assert second.constrain_findings_schema is True
        assert configs["first"].temperature == 0.3

    def test_no_environment_variable_can_redirect_a_voter(self, tmp_path: Path) -> None:
        """The overlay is the one place a voter's endpoint is set."""
        config = load_review_voters(_write(tmp_path)).endpoint_configs()["second"]

        assert config.env_var == ""
        identity = reviewer_identity(
            "second", config, {"LLM_LOCAL_STUDIO_PLANNER_URL": "http://elsewhere:1"}
        )
        assert identity == "http://voter-b.example:8130#served"

    def test_endpoint_url_voter_and_declared_model(self, tmp_path: Path) -> None:
        path = _with_second(
            tmp_path,
            endpoint_url='"https://models.example/v1/chat/completions"',
            model_id_source="declared",
            api_model_id='"vendor/model-x"',
            required="false",
            timeout_seconds=60,
        )
        roster = load_review_voters(path)

        voter = roster.get("second")
        assert voter is not None
        assert voter.base_url == "https://models.example"
        assert roster.required_ids == frozenset({"first"})
        config = voter.endpoint_config()
        assert config.model_id_source == "declared"
        assert config.api_model_id == "vendor/model-x"

    def test_changing_the_backend_changes_the_model_and_nothing_else(
        self, tmp_path: Path
    ) -> None:
        """The overlay-only model swap the ruling asks for."""
        before = load_review_voters(_write(tmp_path)).get("second")
        swapped = _write(
            tmp_path, _VOTERS.replace("backend_id: lab-b", "backend_id: lab-a")
        )
        after = load_review_voters(swapped).get("second")

        assert before is not None and after is not None
        assert before.base_url == "http://voter-b.example:8130"
        assert after.base_url == "http://voter-a.example:8000"
        assert after.voter.temperature == before.voter.temperature

    def test_handle_is_pure_over_the_two_texts(self) -> None:
        request = ModelReviewVotersOverlayRequest(
            overlay_yaml=_VOTERS,
            overlay_source="voters.yaml",
            backend_overlay_yaml=_BIFROST,
            backend_overlay_source="bifrost.yaml",
        )

        assert handle(request) == handle(request)
        assert handle(request).voter_ids == ["first", "second"]

    def test_probe_targets_for_the_workflow_preflight(self, tmp_path: Path) -> None:
        roster = load_review_voters(_write(tmp_path))

        assert probe_target_lines(roster) == [
            "TARGET|first|voter-a.example|8000|http://voter-a.example:8000",
            "TARGET|second|voter-b.example|8130|http://voter-b.example:8130",
        ]


# ---------------------------------------------------------------------------
# Validation: every refusal names the voter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    @pytest.mark.parametrize(
        ("fields", "fragment"),
        [
            (
                {
                    "backend_id": "lab-b",
                    "endpoint_url": '"http://x:1"',
                    "required": "true",
                    "timeout_seconds": 5,
                },
                "exactly one of backend_id or endpoint_url",
            ),
            (
                {"required": "true", "timeout_seconds": 5},
                "exactly one of backend_id or endpoint_url",
            ),
            (
                {
                    "backend_id": "lab-b",
                    "model_id_source": "declared",
                    "required": "true",
                    "timeout_seconds": 5,
                },
                "no api_model_id",
            ),
            (
                {
                    "backend_id": "lab-b",
                    "api_model_id": "m",
                    "required": "true",
                    "timeout_seconds": 5,
                },
                "must not also declare api_model_id",
            ),
            (
                {
                    "backend_id": "lab-b",
                    "required": "true",
                    "timeout_seconds": 5,
                    "temprature": 0.2,
                },
                "temprature",
            ),
            (
                {
                    "backend_id": "lab-b",
                    "required": "true",
                    "timeout_seconds": 5,
                    "top_p": 0,
                },
                "top_p",
            ),
            ({"backend_id": "lab-b", "timeout_seconds": 5}, "required"),
        ],
    )
    def test_malformed_voter_is_refused_naming_it(
        self, tmp_path: Path, fields: dict[str, object], fragment: str
    ) -> None:
        roster = _refused(_with_second(tmp_path, **fields))

        assert roster.error_voter_id == "second"
        assert roster.error_message.startswith("review voter 'second': ")
        assert fragment in roster.error_message

    def test_unknown_backend_names_the_voter_and_the_bound_backends(
        self, tmp_path: Path
    ) -> None:
        path = _write(
            tmp_path, _VOTERS.replace("backend_id: lab-b", "backend_id: lab-gone")
        )
        message = _refused(path).error_message
        assert "review voter 'second'" in message
        assert "'lab-gone' is not bound" in message
        assert "lab-a" in message

    def test_backend_without_endpoint_names_the_voter(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, _VOTERS.replace("backend_id: lab-b", "backend_id: lab-unbound")
        )
        assert re.search(r"'second'.*no endpoint_url", _refused(path).error_message)

    def test_duplicate_voter_ids_are_refused(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _VOTERS.replace("voter_id: second", "voter_id: first"))
        assert re.search("repeated: \\['first'\\]", _refused(path).error_message)

    def test_wrong_schema_version_is_refused(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _VOTERS.replace("review_voters_overlay.v1", "v0"))
        assert re.search("schema_version", _refused(path).error_message)

    def test_an_overlay_with_no_required_voter_is_refused(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _VOTERS.replace("required: true", "required: false"))
        assert re.search(
            "at least one voter must be required", _refused(path).error_message
        )

    def test_backend_id_without_backend_overlay_is_refused(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, _VOTERS.replace("backend_overlay: bifrost.yaml\n", ""))
        assert re.search("no backend_overlay", _refused(path).error_message)

    def test_backend_overlay_of_another_schema_is_refused(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            bifrost=_BIFROST.replace(
                "bifrost_lane_overlay.v3", "bifrost_lane_overlay.v2"
            ),
        )
        assert re.search(
            r"expected 'bifrost_lane_overlay\.v3'", _refused(path).error_message
        )

    def test_missing_overlay_file_is_refused(self, tmp_path: Path) -> None:
        assert re.search("not found", _refused(tmp_path / "absent.yaml").error_message)

    def test_a_voter_may_not_shadow_a_registry_key(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, _VOTERS.replace("voter_id: second", "voter_id: qwen3-review")
        )
        configs = load_review_voters(path).endpoint_configs()
        with pytest.raises(
            ValueError, match=r"'qwen3-review'.*already a model_registry\.yaml key"
        ):
            adapter_ai_reviewer.register_review_voters(configs)


# ---------------------------------------------------------------------------
# The gate: cli_review --voters-overlay
# ---------------------------------------------------------------------------

_CLI = "omniintelligence.review_pairing.cli_review"


@pytest.mark.unit
class TestCliOverlayMode:
    def _plan(self, tmp_path: Path) -> Path:
        plan = tmp_path / "plan.md"
        plan.write_text("# change", encoding="utf-8")
        return plan

    def test_a_voter_removed_from_the_overlay_is_not_called(
        self, tmp_path: Path
    ) -> None:
        """AC1: the gate's roster is the overlay and nothing else."""
        third = textwrap.indent(
            '- voter_id: third\n  endpoint_url: "http://voter-c.example:9000"\n'
            "  required: true\n  timeout_seconds: 60\n",
            "  ",
        )
        reach = {"first": True, "second": True, "third": True}

        def _called(overlay_text: str) -> list[str]:
            overlay = _write(tmp_path, overlay_text)
            parse = AsyncMock(side_effect=lambda _content, model, **_: _success(model))
            with (
                patch(f"{_CLI}.probe_local_reachability", return_value=reach),
                patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
                patch(f"{_CLI}.llm_async_parse_raw", parse),
            ):
                code = main(
                    [
                        "--file",
                        str(self._plan(tmp_path)),
                        "--voters-overlay",
                        str(overlay),
                    ]
                )
            assert code == 0
            return [c.kwargs["model"] for c in parse.await_args_list]

        assert _called(_VOTERS + third) == ["first", "second", "third"]
        assert _called(_VOTERS) == ["first", "second"]

    def test_voters_are_called_in_overlay_order_and_pass(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _write(tmp_path)
        parse = AsyncMock(side_effect=lambda _content, model, **_: _success(model))
        with (
            patch(
                f"{_CLI}.probe_local_reachability",
                return_value={"first": True, "second": True},
            ),
            patch(
                f"{_CLI}.resolve_served_model_id", side_effect=["Model-A", "Model-B"]
            ),
            patch(f"{_CLI}.llm_async_parse_raw", parse),
        ):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 0
        assert [c.kwargs["model"] for c in parse.await_args_list] == ["first", "second"]
        err = capsys.readouterr().err
        assert (
            "Review voter 'second' -> http://voter-b.example:8130 serves model Model-B"
            in err
        )

    def test_unreachable_required_voter_fails_naming_it_and_calls_nobody(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _write(tmp_path)
        parse = AsyncMock(side_effect=lambda _content, model, **_: _success(model))
        with (
            patch(
                f"{_CLI}.probe_local_reachability",
                return_value={"first": True, "second": False},
            ),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model-A"),
            patch(f"{_CLI}.llm_async_parse_raw", parse),
        ):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 2
        parse.assert_not_awaited()
        err = capsys.readouterr().err
        assert (
            "required review voter 'second' is unreachable (second at voter-b.example:8130)"
            in err
        )
        assert "NO VERDICT" in err

    def test_required_voter_that_fails_its_call_fails_the_run_naming_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Three voters, quorum met by two, the required third failed: exit 2."""
        overlay = _write(
            tmp_path,
            _VOTERS
            + textwrap.indent(
                '- voter_id: third\n  endpoint_url: "http://voter-c.example:9000"\n'
                "  required: true\n  timeout_seconds: 60\n",
                "  ",
            ),
        )

        def _vote(content: str, model: str, **_: object) -> ModelExternalReviewResult:
            if model == "third":
                return _failure(model, "HTTP 500")
            return _success(model)

        with (
            patch(
                f"{_CLI}.probe_local_reachability",
                return_value={"first": True, "second": True, "third": True},
            ),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
            patch(f"{_CLI}.llm_async_parse_raw", AsyncMock(side_effect=_vote)),
        ):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 2
        assert (
            "required review voter 'third' did not vote: HTTP 500"
            in capsys.readouterr().err
        )

    def test_optional_voter_lost_leaves_the_required_quorum_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _write(
            tmp_path,
            _VOTERS
            + textwrap.indent(
                '- voter_id: extra\n  endpoint_url: "http://voter-c.example:9000"\n'
                "  required: false\n  timeout_seconds: 60\n",
                "  ",
            ),
        )
        parse = AsyncMock(side_effect=lambda _content, model, **_: _success(model))
        with (
            patch(
                f"{_CLI}.probe_local_reachability",
                return_value={"first": True, "second": True, "extra": False},
            ),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
            patch(f"{_CLI}.llm_async_parse_raw", parse),
        ):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 0
        assert (
            "WARNING: optional review voter 'extra' is unreachable"
            in capsys.readouterr().err
        )

    def test_one_required_voter_is_still_no_quorum(self, tmp_path: Path) -> None:
        """The overlay cannot lower the quorum: one voter is degraded, exit 2."""
        overlay = _with_second(
            tmp_path, backend_id="lab-b", required="false", timeout_seconds=5
        )
        parse = AsyncMock(side_effect=lambda _content, model, **_: _success(model))
        with (
            patch(
                f"{_CLI}.probe_local_reachability",
                return_value={"first": True, "second": False},
            ),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
            patch(f"{_CLI}.llm_async_parse_raw", parse),
        ):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 2

    def test_invalid_overlay_fails_before_any_review_naming_the_voter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _write(
            tmp_path, _VOTERS.replace("backend_id: lab-b", "backend_id: lab-gone")
        )
        parse = AsyncMock()
        with patch(f"{_CLI}.llm_async_parse_raw", parse):
            code = main(
                ["--file", str(self._plan(tmp_path)), "--voters-overlay", str(overlay)]
            )

        assert code == 1
        parse.assert_not_awaited()
        assert (
            "ERROR: review voters overlay: review voter 'second'"
            in capsys.readouterr().err
        )

    def test_model_flag_and_overlay_are_exclusive(self, tmp_path: Path) -> None:
        code = main(
            [
                "--file",
                str(self._plan(tmp_path)),
                "--voters-overlay",
                str(_write(tmp_path)),
                "--model",
                "qwen3-review",
            ]
        )
        assert code == 1


# ---------------------------------------------------------------------------
# Retry budget reads the overlay's own timeouts
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryBudgetOverlay:
    def test_budget_is_computed_from_overlay_timeouts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = retry_budget_main(
            [
                "--voters-overlay",
                str(_write(tmp_path)),
                "--job-timeout-seconds",
                "3600",
                "--setup-overhead-seconds",
                "300",
            ]
        )

        assert code == 0
        err = capsys.readouterr().err
        assert "second: 2 attempts x 300s" in err
        assert "first:" in err

    def test_budget_over_the_ceiling_fails(self, tmp_path: Path) -> None:
        code = retry_budget_main(
            ["--voters-overlay", str(_write(tmp_path)), "--job-timeout-seconds", "100"]
        )
        assert code == 1

    def test_invalid_overlay_fails_the_budget_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _write(
            tmp_path, _VOTERS.replace("backend_id: lab-b", "backend_id: lab-gone")
        )
        code = retry_budget_main(
            ["--voters-overlay", str(overlay), "--job-timeout-seconds", "3600"]
        )
        assert code == 1
        assert "review voter 'second'" in capsys.readouterr().err


def _anthropic_overlay(tmp_path: Path, **overrides: object) -> Path:
    fields: dict[str, object] = {
        "provider": "anthropic",
        "model": "claude-sonnet-5-5",
        "api_key_env": _REVIEW_ENV_NAME,
        "excluded_repositories": '["private-docs"]',
        "required": "true",
        "timeout_seconds": 30,
        "max_retries": 0,
        "temperature": 0.4,
        "review_focus": '"Inspect contracts; keep reviewing the whole change."',
    }
    fields.update(overrides)
    return _with_second(tmp_path, **fields)


def _message(
    text: str = "[]", *, input_tokens: int = 100, output_tokens: int = 5
) -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "stop_reason": "end_turn",
    }


@pytest.mark.unit
class TestAnthropicVoter:
    @pytest.fixture
    def api(self, monkeypatch: pytest.MonkeyPatch):
        """Intercept the real adapter's HTTP boundary, never a live provider."""
        original = httpx.AsyncClient
        monkeypatch.setenv(_REVIEW_ENV_NAME, "synthetic-test-credential")

        def install(handler):
            monkeypatch.setattr(
                httpx,
                "AsyncClient",
                lambda **kwargs: original(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            )

        return install

    def _register(self, tmp_path: Path, **overrides: object):
        roster = load_review_voters(_anthropic_overlay(tmp_path, **overrides))
        assert roster.ok, roster.error_message
        adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())
        return roster

    def test_messages_api_receipt_and_focus(self, tmp_path: Path, api) -> None:
        self._register(tmp_path)
        requests: list[httpx.Request] = []

        def reply(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=_message())

        api(reply)
        result = asyncio.run(run_review("diff", ["second"], review_type="pr"))
        receipt = result.results[0]
        assert receipt.success, receipt.error
        assert receipt.input_tokens == 100
        assert receipt.output_tokens == 5
        assert receipt.reviewer_identity == "anthropic#id=claude-sonnet-5-5"
        assert len(requests) == 1
        request = requests[0]
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "synthetic-test-credential"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = json.loads(request.content)
        assert payload["model"] == "claude-sonnet-5-5"
        assert payload["temperature"] == 0.4
        assert "Inspect contracts" in payload["system"]
        assert payload["messages"][0]["role"] == "user"
        assert "diff" in payload["messages"][0]["content"]
        assert "synthetic-test-credential" not in result.model_dump_json()

    def test_provider_route_is_resolved_and_called_from_overlay(
        self, tmp_path: Path, api
    ) -> None:
        path = _anthropic_overlay(tmp_path)
        path.write_text(
            path.read_text().replace(
                "https://api.anthropic.com", "https://review-api.example"
            )
        )
        roster = load_review_voters(path)
        assert roster.ok, roster.error_message
        adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())
        requests: list[httpx.Request] = []

        def reply(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=_message())

        api(reply)
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        assert result.success, result.error
        assert str(requests[0].url) == "https://review-api.example/v1/messages"
        assert (
            probe_target_lines(roster)[1]
            == "TARGET|second|review-api.example|443|https://review-api.example"
        )

    def test_missing_provider_route_fails_closed_naming_voter(
        self, tmp_path: Path
    ) -> None:
        path = _anthropic_overlay(tmp_path)
        path.write_text(
            path.read_text().replace(
                'provider_endpoints:\n  anthropic: "https://api.anthropic.com"\n', ""
            )
        )
        roster = _refused(path)
        assert roster.error_voter_id == "second"
        assert "provider_endpoints" in roster.error_message

    def test_cloud_route_requires_https(self, tmp_path: Path) -> None:
        path = _anthropic_overlay(tmp_path)
        path.write_text(
            path.read_text().replace(
                "https://api.anthropic.com", "http://review-api.example"
            )
        )
        roster = _refused(path)
        assert roster.error_voter_id == "second"
        assert "requires an HTTPS base URL" in roster.error_message

    def test_cli_calls_cloud_voter_without_lab_probes(
        self, tmp_path: Path, api, capsys: pytest.CaptureFixture[str]
    ) -> None:
        overlay = _anthropic_overlay(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# change", encoding="utf-8")
        api(lambda _request: httpx.Response(200, json=_message()))
        real_parse = adapter_ai_reviewer.async_parse_raw

        async def review(content: str, *, model: str, **kwargs: object):
            if model == "first":
                return _success(model)
            return await real_parse(content, model=model, **kwargs)

        with (
            patch(f"{_CLI}.probe_local_reachability", return_value={"first": True}),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model-A") as served,
            patch(f"{_CLI}.llm_async_parse_raw", side_effect=review),
        ):
            assert main(["--file", str(plan), "--voters-overlay", str(overlay)]) == 0
        assert served.call_count == 1
        assert served.call_args.args == ("http://voter-a.example:8000",)
        receipt = json.loads(capsys.readouterr().out)
        assert receipt["results"][1]["input_tokens"] == 100
        assert receipt["quorum"]["quorum_met"] is True

    def test_missing_key_fails_closed_with_voter_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        overlay = _anthropic_overlay(tmp_path)
        monkeypatch.delenv(_REVIEW_ENV_NAME, raising=False)
        # A different credential must never be silently substituted.
        monkeypatch.setenv("ANTHROPIC_API_KEY", "wrong-credential")
        plan = tmp_path / "plan.md"
        plan.write_text("# change", encoding="utf-8")
        real_parse = adapter_ai_reviewer.async_parse_raw

        async def review(content: str, *, model: str, **kwargs: object):
            return (
                _success(model)
                if model == "first"
                else await real_parse(content, model=model, **kwargs)
            )

        with (
            patch(f"{_CLI}.probe_local_reachability", return_value={"first": True}),
            patch(f"{_CLI}.resolve_served_model_id", return_value="Model-A"),
            patch(f"{_CLI}.llm_async_parse_raw", side_effect=review),
            patch("httpx.AsyncClient") as http,
        ):
            assert main(["--file", str(plan), "--voters-overlay", str(overlay)]) == 2
        http.assert_not_called()
        captured = capsys.readouterr()
        assert "required review voter 'second' did not vote" in captured.err
        assert _REVIEW_ENV_NAME in captured.err
        assert "wrong-credential" not in captured.out + captured.err

    @pytest.mark.parametrize("status", [429, 503])
    def test_transient_failure_retries_with_configured_budget(
        self, tmp_path: Path, api, status: int
    ) -> None:
        self._register(tmp_path, max_retries=1)
        requests: list[httpx.Request] = []

        def reply(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return (
                httpx.Response(status, text="private error")
                if len(requests) == 1
                else httpx.Response(200, json=_message())
            )

        api(reply)
        with patch.object(
            adapter_ai_reviewer.asyncio, "sleep", new_callable=AsyncMock
        ) as sleep:
            result = asyncio.run(
                adapter_ai_reviewer.async_parse_raw("diff", model="second")
            )
        assert result.success, result.error
        assert len(requests) == 2
        sleep.assert_awaited_once_with(2.0)
        assert result.input_tokens == 100

    def test_timeout_exhausts_retries_without_exposing_credentials(
        self, tmp_path: Path, api
    ) -> None:
        self._register(tmp_path, max_retries=1)
        attempts = 0

        def reply(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            assert request.extensions["timeout"]["read"] == 30
            raise httpx.ReadTimeout("synthetic-test-credential", request=request)

        api(reply)
        with patch.object(adapter_ai_reviewer.asyncio, "sleep", new_callable=AsyncMock):
            result = asyncio.run(
                adapter_ai_reviewer.async_parse_raw("diff", model="second")
            )
        assert not result.success
        assert attempts == 2
        assert "ReadTimeout" in (result.error or "")
        assert "synthetic-test-credential" not in result.model_dump_json()

    def test_per_attempt_deadline_cancels_a_silent_response(
        self, tmp_path: Path, api
    ) -> None:
        self._register(tmp_path, timeout_seconds=0.01)

        async def reply(_request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(10)
            return httpx.Response(200, json=_message())

        api(reply)
        with pytest.raises(
            RuntimeError, match=r"Claude API transport failed \(TimeoutError\)"
        ):
            asyncio.run(
                adapter_ai_reviewer.call_model("system", "diff", model_key="second")
            )

    def test_authentication_failure_is_not_retried_or_logged(
        self, tmp_path: Path, api
    ) -> None:
        self._register(tmp_path, max_retries=2)
        attempts = 0

        def reply(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(401, text="synthetic-test-credential")

        api(reply)
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        assert not result.success
        assert attempts == 1
        assert result.error == "Claude API call failed (HTTP 401)"

    @pytest.mark.parametrize(
        ("message", "extra"),
        [
            ("`temperature` is deprecated for this model", ""),
            ("long message " * 100, ""),
            ("bad\n  request\tvalue", "synthetic-test-credential"),
        ],
    )
    def test_provider_error_summary(
        self,
        tmp_path: Path,
        api: Callable[[Callable[[httpx.Request], httpx.Response]], None],
        message: str,
        extra: str,
    ) -> None:
        self._register(tmp_path, max_retries=2)
        attempts = 0

        def reply(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(
                400,
                json={
                    "type": "error",
                    "extra": extra,
                    "error": {"type": "invalid_request_error", "message": message},
                },
            )

        api(reply)
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        suffix = " ".join(f"invalid_request_error: {message}".split())[:200]
        assert result.error == f"Claude API call failed (HTTP 400): {suffix}"
        assert len(suffix) <= 200
        assert attempts == 1
        assert "synthetic-test-credential" not in (result.error or "")

    @pytest.mark.parametrize(
        "body",
        [
            None,
            [],
            {},
            {"error": []},
            {"error": {}},
            {"error": {"type": "invalid_request_error"}},
            {"error": {"message": "bad request"}},
            {"error": {"type": 1, "message": "bad request"}},
            {"error": {"type": "invalid_request_error", "message": None}},
        ],
    )
    def test_malformed_provider_error_keeps_status_only(self, body: object) -> None:
        response = httpx.Response(400, content=json.dumps(body))
        assert adapter_ai_reviewer._claude_error_summary(response) == (
            "Claude API call failed (HTTP 400)"
        )

    def test_parse_retry_accumulates_tokens_and_separate_reviews_reset(
        self, tmp_path: Path, api
    ) -> None:
        self._register(tmp_path)
        replies = iter([_message("not JSON"), _message(), _message()])
        api(lambda _request: httpx.Response(200, json=next(replies)))
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        assert result.success
        assert (result.input_tokens, result.output_tokens) == (200, 10)
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        assert result.success
        assert (result.input_tokens, result.output_tokens) == (100, 5)

    def test_concurrent_reviews_keep_separate_usage(self, tmp_path: Path, api) -> None:
        self._register(tmp_path)

        async def reply(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            count = 100 if "alpha" in payload["messages"][0]["content"] else 200
            await asyncio.sleep(0)
            return httpx.Response(200, json=_message(input_tokens=count))

        async def reviews():
            return await asyncio.gather(
                adapter_ai_reviewer.async_parse_raw("alpha", model="second"),
                adapter_ai_reviewer.async_parse_raw("beta", model="second"),
            )

        api(reply)
        first, second = asyncio.run(reviews())
        assert first.success and second.success
        assert (first.input_tokens, second.input_tokens) == (100, 200)

    def test_chunk_usage_accumulates_in_one_receipt(self, tmp_path: Path, api) -> None:
        self._register(tmp_path)
        api(lambda _request: httpx.Response(200, json=_message()))
        with patch.object(
            adapter_ai_reviewer, "_review_chunks", return_value=["first", "second"]
        ):
            result = asyncio.run(
                adapter_ai_reviewer.async_parse_raw("diff", model="second")
            )
        assert result.success
        assert (result.input_tokens, result.output_tokens) == (200, 10)

    @pytest.mark.parametrize(
        "body", [_message("not JSON"), {**_message(), "stop_reason": "max_tokens"}]
    )
    def test_failed_review_keeps_usage(
        self, tmp_path: Path, api, body: dict[str, object]
    ) -> None:
        self._register(tmp_path)
        api(lambda _request: httpx.Response(200, json=body))
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model="second")
        )
        assert not result.success
        assert result.input_tokens >= 100
        assert result.output_tokens >= 5

    def test_cloud_refuses_overlay_excluded_repository_before_http(
        self, tmp_path: Path, api
    ) -> None:
        self._register(tmp_path)
        with patch("httpx.AsyncClient") as http:
            result = asyncio.run(
                adapter_ai_reviewer.async_parse_raw(
                    "private diff",
                    model="second",
                    repository="acme/private-docs",
                )
            )
        assert not result.success
        http.assert_not_called()

    def test_cloud_voter_has_a_workflow_target_but_is_not_a_local_model(
        self, tmp_path: Path
    ) -> None:
        roster = self._register(tmp_path)
        assert "second" not in adapter_ai_reviewer._LOCAL_MODEL_KEYS
        assert probe_target_lines(roster) == [
            "TARGET|first|voter-a.example|8000|http://voter-a.example:8000",
            "TARGET|second|api.anthropic.com|443|https://api.anthropic.com",
        ]

    def test_aliases_and_different_keys_do_not_supply_distinct_votes(
        self, tmp_path: Path
    ) -> None:
        roster = self._register(tmp_path)
        config = roster.endpoint_configs()["second"]
        other_key = config.model_copy(update={"api_key_env": "ANOTHER_REVIEW_KEY"})
        identity = reviewer_identity("second", config, {})
        assert identity == reviewer_identity("alias", other_key, {})
        result = asyncio.run(run_review("diff", []))
        result = result.model_copy(
            update={
                "results": [
                    _success("second").model_copy(
                        update={"reviewer_identity": identity}
                    ),
                    _success("alias").model_copy(
                        update={"reviewer_identity": identity}
                    ),
                ]
            }
        )
        assert not evaluate_quorum(result, ModelReviewQuorumPolicy()).quorum_met
        another_model = config.model_copy(update={"api_model_id": "another-sonnet"})
        assert identity != reviewer_identity("second", another_model, {})

    @pytest.mark.parametrize(
        "overrides",
        [
            {"model": '""'},
            {"api_key_env": '""'},
            {"api_key_env": '"not-an-env-name"'},
            {"endpoint_url": '"https://elsewhere.example"'},
            {"backend_id": "lab-b"},
            {"model_id_source": "served"},
            {"api_model_id": "other-model"},
            {"enable_thinking": "true"},
            {"reasoning_effort": "high"},
            {"constrain_findings_schema": "true"},
            {"temperature": 1.5},
            {"top_p": 0.8},
        ],
    )
    def test_invalid_anthropic_shape_names_voter(
        self, tmp_path: Path, overrides: dict[str, object]
    ) -> None:
        refused = _refused(_anthropic_overlay(tmp_path, **overrides))
        assert refused.error_voter_id == "second"
