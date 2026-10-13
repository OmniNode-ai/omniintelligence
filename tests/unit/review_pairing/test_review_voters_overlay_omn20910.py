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

import re
import textwrap
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
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
