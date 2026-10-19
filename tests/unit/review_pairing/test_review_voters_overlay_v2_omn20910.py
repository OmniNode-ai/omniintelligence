# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""review_voters_overlay.v2: personas, canonical identity, overflow identity (OMN-20910).

Plan ticket 8 of the cost-shaped Hostile Reviewer. v2 adds, per voter:

* ``personas`` -- at most three ``{persona_id, focus, tier, mode}`` entries.
  Personas of one model are ONE reviewer: they widen that voter's coverage and
  never add a vote;
* ``claude_gateway`` -- the voter is served by a Claude gateway host. Every
  gateway host serving one model has the one identity ``anthropic#id=<model>``;
* a resolver refusal of an overflow onto another voter's own endpoint, so an
  overflow cannot become a second vote for an identity already counted;
* deadline accounting across personas, chunks and attempts.

v1 documents stay accepted, resolve exactly as before, and refuse every v2 field.
Every refusal here has a positive control beside it.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter_roster import (
    ModelReviewVoterRoster,
)
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelReviewQuorumPolicy,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from omniintelligence.review_pairing.quorum import evaluate_quorum
from omniintelligence.review_pairing.retry_budget import (
    assert_budget_within_ceiling,
    compute_sequential_worst_case,
)
from omniintelligence.review_pairing.retry_budget import main as retry_budget_main
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity

pytestmark = pytest.mark.unit

_V1 = "review_voters_overlay.v1"
_V2 = "review_voters_overlay.v2"
_SONNET = "claude-sonnet-5-5"
_OPUS = "claude-opus-5-5"
_LAB_URL = "http://lab-voter.example:8000"
_GATEWAY_A = "http://gateway-a.example:8200"
_GATEWAY_B = "http://gateway-b.example:8200"
_OTHER_LAB = "http://overflow-lab.example:8100"

_BIFROST = textwrap.dedent(
    f"""\
    schema_version: "bifrost_lane_overlay.v3"
    lane: dev
    locale: lab
    backends:
      - backend_id: lab-a
        endpoint_url: "{_LAB_URL}/v1/chat/completions"
        served_model_id: "Model-A"
    """
)

_LAB_VOTER = textwrap.indent(
    textwrap.dedent(
        """\
        - voter_id: lab
          backend_id: lab-a
          required: true
          timeout_seconds: 120
        """
    ),
    "  ",
)

_PERSONAS = textwrap.dedent(
    """\
        personas:
          - persona_id: correctness
            focus: "Correctness first."
            tier: required
            mode: inline
          - persona_id: security
            focus: "Security and contracts."
            tier: budgeted
            mode: inline
          - persona_id: tests
            focus: "Test gaps."
            tier: budgeted
            mode: advisory
    """
)


def _gateway_voter(
    voter_id: str = "sonnet",
    *,
    host: str = _GATEWAY_A,
    model: str = _SONNET,
    extra: str = "",
) -> str:
    return textwrap.indent(
        textwrap.dedent(
            f"""\
            - voter_id: {voter_id}
              endpoint_url: "{host}/v1/chat/completions"
              claude_gateway: true
              model_id_source: declared
              api_model_id: {model}
              required: true
              timeout_seconds: 300
            """
        ),
        "  ",
    ) + textwrap.indent(textwrap.dedent(extra), "    ")


def _write(
    tmp_path: Path,
    *voters: str,
    schema: str = _V2,
    head: str = "",
    name: str = "v.yaml",
) -> Path:
    (tmp_path / "bifrost.yaml").write_text(_BIFROST, encoding="utf-8")
    path = tmp_path / name
    path.write_text(
        f'schema_version: "{schema}"\nbackend_overlay: bifrost.yaml\n{head}voters:\n'
        + "".join(voters),
        encoding="utf-8",
    )
    return path


def _ok(path: Path) -> ModelReviewVoterRoster:
    roster = load_review_voters(path)
    assert roster.ok, roster.error_message
    return roster


def _refused(path: Path) -> ModelReviewVoterRoster:
    roster = load_review_voters(path)
    assert not roster.ok, "the overlay was expected to be refused"
    assert roster.voters == ()
    return roster


def _finding(model: str) -> ModelReviewFindingObserved:
    return ModelReviewFindingObserved(
        finding_id=uuid4(),
        repo="OmniNode-ai/omniintelligence",
        pr_id=1,
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
        observed_at=datetime(2026, 10, 19, 2, 0, tzinfo=UTC),
    )


def _vote(model: str, identity: str) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=[_finding(model)],
        result_count=1,
        reviewer_identity=identity,
    )


def _quorum_met(*votes: ModelExternalReviewResult) -> bool:
    multi = ModelMultiReviewResult(
        models_attempted=[v.model for v in votes],
        models_succeeded=[v.model for v in votes],
        results=list(votes),
        total_findings=len(votes),
    )
    return evaluate_quorum(multi, ModelReviewQuorumPolicy()).quorum_met


# ---------------------------------------------------------------------------
# v1 stays accepted; v2 fields belong to v2
# ---------------------------------------------------------------------------


class TestSchemaVersions:
    def test_a_v1_overlay_still_resolves_with_the_v1_numbers(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(_write(tmp_path, _LAB_VOTER, schema=_V1))
        [voter] = roster.voters
        config = voter.endpoint_config()
        assert voter.voter.personas == ()
        assert (config.inline_persona_count, config.review_attempts_per_call) == (1, 1)
        assert config.identity_family == ""

    def test_a_v2_overlay_without_personas_resolves(self, tmp_path: Path) -> None:
        roster = _ok(_write(tmp_path, _LAB_VOTER))
        assert roster.voter_ids == ["lab"]

    def test_an_unknown_schema_version_is_refused(self, tmp_path: Path) -> None:
        refused = _refused(
            _write(tmp_path, _LAB_VOTER, schema="review_voters_overlay.v3")
        )
        assert "schema_version" in refused.error_message

    @pytest.mark.parametrize(
        "voter_id",
        [
            pytest.param("lab", id="personas"),
            pytest.param("sonnet", id="claude_gateway"),
        ],
    )
    def test_v2_fields_are_refused_under_v1_naming_the_voter(
        self, tmp_path: Path, voter_id: str
    ) -> None:
        voter = (
            _LAB_VOTER + textwrap.indent(textwrap.dedent(_PERSONAS), "    ")
            if voter_id == "lab"
            else _LAB_VOTER + _gateway_voter()
        )
        refused = _refused(_write(tmp_path, voter, schema=_V1, name="v1.yaml"))
        assert "review_voters_overlay.v2" in refused.error_message
        assert refused.error_voter_id == voter_id
        # Positive control: the same text is accepted under v2.
        assert _ok(_write(tmp_path, voter, schema=_V2, name="v2.yaml")).voters


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------


class TestPersonas:
    def test_personas_with_tier_and_mode_reach_the_resolved_voter(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(_write(tmp_path, _LAB_VOTER, _gateway_voter(extra=_PERSONAS)))
        sonnet = roster.get("sonnet")
        assert sonnet is not None
        got = [(p.persona_id, p.tier, p.mode, p.focus) for p in sonnet.voter.personas]
        assert got == [
            ("correctness", "required", "inline", "Correctness first."),
            ("security", "budgeted", "inline", "Security and contracts."),
            ("tests", "budgeted", "advisory", "Test gaps."),
        ]
        assert "personas=3" in sonnet.describe()

    def test_four_personas_are_refused(self, tmp_path: Path) -> None:
        four = _PERSONAS + textwrap.indent(
            textwrap.dedent(
                """\
                - persona_id: extra
                  focus: "x"
                  tier: budgeted
                  mode: advisory
                """
            ),
            "  ",
        )
        refused = _refused(_write(tmp_path, _gateway_voter(extra=four), _LAB_VOTER))
        assert refused.error_voter_id == "sonnet"
        # Positive control: three are accepted.
        _ok(
            _write(
                tmp_path, _gateway_voter(extra=_PERSONAS), _LAB_VOTER, name="ok.yaml"
            )
        )

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            pytest.param("tier: required", "tier: budgeted", id="first-not-required"),
            pytest.param(
                "persona_id: security", "persona_id: correctness", id="dup-id"
            ),
            pytest.param(
                "tier: budgeted\n    mode: inline",
                "tier: gold\n    mode: inline",
                id="tier",
            ),
            pytest.param(
                "mode: inline\n  - persona_id: security",
                "mode: batch\n  - persona_id: security",
                id="mode",
            ),
            pytest.param('focus: "Test gaps."', 'focus: ""', id="blank-focus"),
        ],
    )
    def test_a_malformed_persona_list_is_refused_naming_the_voter(
        self, tmp_path: Path, old: str, new: str
    ) -> None:
        personas = _PERSONAS.replace(old, new, 1)
        assert personas != _PERSONAS
        refused = _refused(_write(tmp_path, _gateway_voter(extra=personas), _LAB_VOTER))
        assert refused.error_voter_id == "sonnet"

    def test_the_first_persona_of_a_required_voter_is_an_inline_vote(
        self, tmp_path: Path
    ) -> None:
        personas = _PERSONAS.replace(
            "tier: required\n    mode: inline",
            "tier: required\n    mode: advisory",
            1,
        )
        refused = _refused(_write(tmp_path, _gateway_voter(extra=personas), _LAB_VOTER))
        assert refused.error_voter_id == "sonnet"
        assert "inline" in refused.error_message

    def test_persona_ids_are_unique_across_voters(self, tmp_path: Path) -> None:
        refused = _refused(
            _write(
                tmp_path,
                _gateway_voter("a", extra=_PERSONAS),
                _gateway_voter("b", host=_GATEWAY_B, model=_OPUS, extra=_PERSONAS),
                _LAB_VOTER,
            )
        )
        assert "persona" in refused.error_message


# ---------------------------------------------------------------------------
# Canonical identity
# ---------------------------------------------------------------------------


class TestCanonicalIdentity:
    def test_two_gateway_hosts_serving_one_model_are_one_identity(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(
            _write(
                tmp_path,
                _LAB_VOTER,
                _gateway_voter("sonnet-a", host=_GATEWAY_A),
                _gateway_voter("sonnet-b", host=_GATEWAY_B),
            )
        )
        configs = roster.endpoint_configs()
        a = reviewer_identity("sonnet-a", configs["sonnet-a"], {})
        b = reviewer_identity("sonnet-b", configs["sonnet-b"], {})
        assert a == b == f"anthropic#id={_SONNET}"
        # Positive control: the lab voter is a different reviewer.
        assert reviewer_identity("lab", configs["lab"], {}) == f"{_LAB_URL}#served"
        assert roster.identities()["sonnet-a"] == roster.identities()["sonnet-b"]
        assert len(set(roster.identities().values())) == 2

    def test_a_vote_served_by_the_second_gateway_host_keeps_the_identity(
        self, tmp_path: Path
    ) -> None:
        extra = f'overflow_endpoint_urls: ["{_GATEWAY_B}/v1/chat/completions"]\n'
        extra += f'claude_gateway_endpoint_urls: ["{_GATEWAY_B}/v1/chat/completions"]\n'
        roster = _ok(_write(tmp_path, _LAB_VOTER, _gateway_voter(extra=extra)))
        config = roster.endpoint_configs()["sonnet"]
        assert config.identity_family == "anthropic"
        assert reviewer_identity("sonnet", config, {}, _GATEWAY_B) == (
            f"anthropic#id={_SONNET}"
        )

    def test_two_gateway_hosts_do_not_meet_the_quorum_with_each_other(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(
            _write(
                tmp_path,
                _LAB_VOTER,
                _gateway_voter("sonnet-a", host=_GATEWAY_A),
                _gateway_voter("sonnet-b", host=_GATEWAY_B),
            )
        )
        ids = roster.identities()
        both = (_vote("sonnet-a", ids["sonnet-a"]), _vote("sonnet-b", ids["sonnet-b"]))
        assert not _quorum_met(*both)
        # Positive control: a different identity does meet it.
        assert _quorum_met(both[0], _vote("lab", ids["lab"]))

    def test_another_model_through_the_gateway_is_another_identity(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(
            _write(
                tmp_path,
                _LAB_VOTER,
                _gateway_voter("sonnet", model=_SONNET),
                _gateway_voter("opus", host=_GATEWAY_B, model=_OPUS),
            )
        )
        ids = roster.identities()
        assert ids["sonnet"] == f"anthropic#id={_SONNET}"
        assert ids["opus"] == f"anthropic#id={_OPUS}"

    def test_a_gateway_vote_overflowed_to_a_lab_endpoint_takes_that_identity(
        self, tmp_path: Path
    ) -> None:
        extra = f'overflow_endpoint_urls: ["{_OTHER_LAB}/v1/chat/completions"]\n'
        roster = _ok(_write(tmp_path, _LAB_VOTER, _gateway_voter(extra=extra)))
        config = roster.endpoint_configs()["sonnet"]
        assert reviewer_identity("sonnet", config, {}, _OTHER_LAB) == (
            f"{_OTHER_LAB}#served"
        )

    @pytest.mark.parametrize(
        "fields",
        [
            "model_id_source: served\n",
            "api_model_id: gpt-lab\n",
            'claude_gateway_endpoint_urls: ["http://not-in-overflow.example:1"]\n',
        ],
    )
    def test_a_malformed_gateway_voter_is_refused_naming_it(
        self, tmp_path: Path, fields: str
    ) -> None:
        voter = _gateway_voter().replace(
            "    model_id_source: declared\n    api_model_id: " + _SONNET + "\n", ""
        )
        key = fields.split(":")[0]
        if key == "claude_gateway_endpoint_urls":
            voter = _gateway_voter(extra=fields)
        else:
            voter += textwrap.indent(fields, "    ")
        refused = _refused(_write(tmp_path, _LAB_VOTER, voter))
        assert refused.error_voter_id == "sonnet"


# ---------------------------------------------------------------------------
# Overflow may not become another voter's vote
# ---------------------------------------------------------------------------


class TestOverflowIdentity:
    def _overflow_onto(self, tmp_path: Path, url: str, schema: str = _V2) -> Path:
        extra = f'overflow_endpoint_urls: ["{url}"]\n'
        return _write(
            tmp_path,
            _LAB_VOTER,
            _gateway_voter(extra=extra),
            schema=schema,
            name=f"{schema[-2:]}-{abs(hash(url))}.yaml",
        )

    @pytest.mark.parametrize(
        "spelling",
        [
            f"{_LAB_URL}/v1/chat/completions",
            f"{_LAB_URL}/v1",
            _LAB_URL.upper().replace("HTTP", "http"),
        ],
    )
    def test_a_sonnet_overflow_onto_the_lab_voters_endpoint_is_refused(
        self, tmp_path: Path, spelling: str
    ) -> None:
        refused = _refused(self._overflow_onto(tmp_path, spelling))
        assert refused.error_voter_id == "sonnet"
        assert "lab" in refused.error_message

    def test_the_refused_overflow_could_not_have_met_the_quorum_anyway(
        self, tmp_path: Path
    ) -> None:
        # Had the call overflowed onto the lab endpoint, the vote would carry
        # the lab voter's identity, and one identity never meets the quorum.
        roster = _ok(_write(tmp_path, _LAB_VOTER, _gateway_voter(), name="plain.yaml"))
        configs = roster.endpoint_configs()
        lab_identity = reviewer_identity("lab", configs["lab"], {})
        overflowed = reviewer_identity("sonnet", configs["sonnet"], {}, _LAB_URL)
        assert overflowed == lab_identity
        assert not _quorum_met(_vote("lab", lab_identity), _vote("sonnet", overflowed))
        # Positive control: the Sonnet vote on its own gateway meets it.
        own = reviewer_identity("sonnet", configs["sonnet"], {})
        assert _quorum_met(_vote("lab", lab_identity), _vote("sonnet", own))

    def test_an_overflow_onto_a_lab_endpoint_nobody_else_votes_from_is_accepted(
        self, tmp_path: Path
    ) -> None:
        roster = _ok(self._overflow_onto(tmp_path, f"{_OTHER_LAB}/v1/chat/completions"))
        sonnet = roster.get("sonnet")
        assert sonnet is not None
        assert sonnet.overflow_base_urls == (_OTHER_LAB,)

    def test_an_overflow_onto_another_voters_gateway_host_is_refused(
        self, tmp_path: Path
    ) -> None:
        extra = f'overflow_endpoint_urls: ["{_GATEWAY_B}/v1/chat/completions"]\n'
        refused = _refused(
            _write(
                tmp_path,
                _LAB_VOTER,
                _gateway_voter("sonnet-a", extra=extra),
                _gateway_voter("sonnet-b", host=_GATEWAY_B),
            )
        )
        assert refused.error_voter_id == "sonnet-a"
        assert "sonnet-b" in refused.error_message

    def test_v1_overlays_are_untouched_by_the_refusal(self, tmp_path: Path) -> None:
        voters = textwrap.dedent(
            f"""\
              - voter_id: lab
                backend_id: lab-a
                required: true
                timeout_seconds: 120
              - voter_id: second
                endpoint_url: "{_GATEWAY_A}/v1/chat/completions"
                overflow_endpoint_urls: ["{_LAB_URL}/v1/chat/completions"]
                required: true
                timeout_seconds: 300
            """
        )
        assert _ok(_write(tmp_path, voters, schema=_V1)).voter_ids == ["lab", "second"]
        # Positive control: the same text under v2 is refused.
        assert (
            _refused(
                _write(tmp_path, voters, schema=_V2, name="v2.yaml")
            ).error_voter_id
            == "second"
        )


# ---------------------------------------------------------------------------
# Deadline accounting across personas, chunks and attempts
# ---------------------------------------------------------------------------


def _timed_voter(extra: str) -> str:
    return _gateway_voter(extra=extra).replace(
        "timeout_seconds: 300", "timeout_seconds: 100\n    max_retries: 0"
    )


def _worst(path: Path, chunk_count: int | None) -> float:
    roster = _ok(path)
    [result] = compute_sequential_worst_case(
        ["sonnet"], configs=roster.endpoint_configs(), chunk_count=chunk_count
    )
    return result.worst_case_seconds


class TestDeadlineAccounting:
    def test_calls_are_chunks_times_inline_personas_times_attempts(
        self, tmp_path: Path
    ) -> None:
        # Two inline personas + one advisory (runs after the gate, not counted),
        # a first reply plus the JSON-ONLY retry = 2 attempts per call.
        extra = "review_deadline_seconds: 7200\n" + _PERSONAS
        path = _write(tmp_path, _LAB_VOTER, _timed_voter(extra))
        config = _ok(path).endpoint_configs()["sonnet"]
        assert (config.inline_persona_count, config.review_attempts_per_call) == (2, 2)
        # 3 chunks x 2 personas x 2 attempts x 100 s
        assert _worst(path, 3) == 1200.0
        # One chunk still pays every persona and attempt: 1 x 2 x 2 x 100 s
        assert _worst(path, 1) == 400.0

    def test_the_same_voter_without_personas_pays_the_attempt_only(
        self, tmp_path: Path
    ) -> None:
        path = _write(
            tmp_path,
            _LAB_VOTER,
            _timed_voter("review_deadline_seconds: 7200\n"),
            name="plain.yaml",
        )
        assert _worst(path, 3) == 600.0  # 3 chunks x 1 persona x 2 attempts

    def test_the_ceiling_still_caps_the_review_and_an_unknown_chunk_count_is_the_ceiling(
        self, tmp_path: Path
    ) -> None:
        extra = "review_deadline_seconds: 900\n" + _PERSONAS
        path = _write(tmp_path, _LAB_VOTER, _timed_voter(extra))
        assert _worst(path, 50) == 900.0
        assert _worst(path, None) == 900.0

    def test_without_a_ceiling_every_persona_and_attempt_still_costs_a_call(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, _LAB_VOTER, _timed_voter(_PERSONAS))
        # one call 100 s, x 2 personas x 2 attempts
        assert _worst(path, 9) == 400.0
        assert _worst(path, None) == 400.0

    def test_v1_numbers_do_not_move(self, tmp_path: Path) -> None:
        voter = _timed_voter("review_deadline_seconds: 7200\n").replace(
            "claude_gateway: true\n    ", ""
        )
        path = _write(tmp_path, _LAB_VOTER, voter, schema=_V1, name="v1.yaml")
        assert _worst(path, 3) == 300.0
        assert _worst(path, 1) == 100.0

    def test_the_budget_check_refuses_a_roster_whose_personas_overrun_the_job(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, _LAB_VOTER, _timed_voter(_PERSONAS))
        configs = _ok(path).endpoint_configs()
        # lab (one 120 s call, 3 retries + backoff) + sonnet 400 s
        assert_budget_within_ceiling(
            ["lab", "sonnet"], job_timeout_seconds=3600.0, configs=configs
        )
        with pytest.raises(AssertionError, match="Retry-budget invariant violated"):
            assert_budget_within_ceiling(
                ["lab", "sonnet"], job_timeout_seconds=600.0, configs=configs
            )

    def test_the_cli_budget_check_reads_the_v2_overlay(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write(tmp_path, _LAB_VOTER, _timed_voter(_PERSONAS))
        argv = ["--voters-overlay", str(path)]
        assert retry_budget_main([*argv, "--job-timeout-seconds", "3600"]) == 0
        assert retry_budget_main([*argv, "--job-timeout-seconds", "600"]) == 1
        assert "Retry-budget invariant violated" in capsys.readouterr().err
