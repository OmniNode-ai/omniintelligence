# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A review voter may name overflow endpoints (OMN-20923).

The Hostile Reviewer's second voter sits on a single-queue host that answers 503
when full and times out when busy; a voter that names an ordered list of
endpoints falls to the next one instead of costing the gate its quorum. The
shipped default stays a single endpoint, so a fork's overlay is unchanged.

* schema -- ``overflow_endpoint_urls`` and ``overflow_after_seconds`` load,
  resolve and validate, and a voter that sets neither is byte-for-byte the
  voter it was;
* call -- full, unavailable, rate-limited, refused and silent endpoints move
  the call on; a rejected request or a last endpoint failing does not;
* identity -- the vote is counted against the host that cast it;
* budget -- the retry budget counts the time spent giving up on the primary.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from omnibase_infra.enums import EnumInfraTransportType
from omnibase_infra.errors import (
    InfraConnectionError,
    InfraRateLimitedError,
    InfraRequestRejectedError,
    InfraTimeoutError,
    InfraUnavailableError,
    ModelTimeoutErrorContext,
)

from omniintelligence.nodes.node_review_voters_overlay_compute.handlers.handler_review_voters_overlay import (
    probe_target_lines,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.retry_budget import (
    compute_sequential_worst_case,
    format_budget_breakdown,
)
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity

pytestmark = [pytest.mark.unit]

_PRIMARY = "http://primary.example:8130"
_OVERFLOW = "http://overflow.example:8000"
_OVERFLOW_2 = "http://overflow-two.example:8000"
_ENV = dict.fromkeys(("LOCAL_LLM_SHARED_SECRET",), "x")


def _overlay(tmp_path: Path, second_extra: str = "") -> Path:
    text = textwrap.dedent(
        """\
        schema_version: "review_voters_overlay.v1"
        voters:
          - voter_id: first
            endpoint_url: "http://first.example:8000/v1/chat/completions"
            required: true
            timeout_seconds: 120
          - voter_id: second
            endpoint_url: "http://primary.example:8130/v1/chat/completions"
            required: true
            timeout_seconds: 300
            max_retries: 1
        """
    )
    path = tmp_path / "voters.yaml"
    path.write_text(text + textwrap.indent(second_extra, "    "), encoding="utf-8")
    return path


_OVERFLOW_FIELDS = textwrap.dedent(
    """\
    overflow_endpoint_urls:
      - "http://overflow.example:8000/v1/chat/completions"
    overflow_after_seconds: 90
    """
)


@pytest.fixture(autouse=True)
def _restore_adapter_state() -> Iterator[None]:
    registry = dict(adapter_ai_reviewer.MODEL_REGISTRY)
    local_keys = adapter_ai_reviewer._LOCAL_MODEL_KEYS
    adapter_ai_reviewer.SERVED_BASE_URLS.clear()
    yield
    adapter_ai_reviewer.MODEL_REGISTRY.clear()
    adapter_ai_reviewer.MODEL_REGISTRY.update(registry)
    adapter_ai_reviewer._LOCAL_MODEL_KEYS = local_keys
    adapter_ai_reviewer.SERVED_BASE_URLS.clear()


class TestSchema:
    def test_a_voter_with_no_overflow_is_the_voter_it_was(self, tmp_path: Path) -> None:
        roster = load_review_voters(_overlay(tmp_path))

        second = roster.get("second")
        assert second is not None
        assert second.voter.overflow_endpoint_urls == ()
        assert second.voter.overflow_after_seconds is None
        assert second.overflow_base_urls == ()
        config = second.endpoint_config()
        assert config.overflow_urls == ()
        assert config.overflow_after_seconds is None
        assert "overflow" not in second.describe()
        assert [line.split("|")[1] for line in probe_target_lines(roster)] == [
            "first",
            "second",
        ]

    def test_overflow_endpoints_resolve_like_the_primary(self, tmp_path: Path) -> None:
        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))

        assert roster.ok, roster.error_message
        second = roster.get("second")
        assert second is not None
        assert second.base_url == _PRIMARY
        assert second.overflow_base_urls == (_OVERFLOW,)
        config = second.endpoint_config()
        assert config.default_url == _PRIMARY
        assert config.overflow_urls == (_OVERFLOW,)
        assert config.overflow_after_seconds == 90
        assert f"overflow -> {_OVERFLOW}" in second.describe()

    def test_an_overflow_endpoint_is_a_probe_and_allowlist_target(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))

        assert probe_target_lines(roster) == [
            "TARGET|first|first.example|8000|http://first.example:8000",
            f"TARGET|second|primary.example|8130|{_PRIMARY}",
            f"TARGET|second+overflow1|overflow.example|8000|{_OVERFLOW}",
        ]

    @pytest.mark.parametrize(
        ("fields", "fragment"),
        [
            ("overflow_after_seconds: 30\n", "declares no overflow_endpoint_urls"),
            (
                'overflow_endpoint_urls: ["http://o.example:1"]\n'
                "overflow_after_seconds: 301\n",
                "exceeds its timeout_seconds",
            ),
            (
                'overflow_endpoint_urls: ["http://o.example:1", "http://o.example:1"]\n',
                "repeats an overflow endpoint",
            ),
            ('overflow_endpoint_urls: ["  "]\n', "blank overflow_endpoint_urls"),
            (
                'overflow_endpoint_urls: ["ftp://o.example:1"]\n',
                "not an http(s) URL",
            ),
            (
                'overflow_endpoint_urls: ["http://o.example:99999999"]\n',
                "invalid port",
            ),
            (
                'overflow_endpoint_urls: ["http://primary.example:8130/chat/completions"]\n',
                "names the voter's own endpoint",
            ),
        ],
    )
    def test_a_malformed_overflow_is_refused_naming_the_voter(
        self, tmp_path: Path, fields: str, fragment: str
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, fields))

        assert not roster.ok
        assert fragment in roster.error
        assert roster.error_voter_id == "second"


class _Reply:
    generated_text = "[]"


def _error(kind: type[Exception]) -> Exception:
    if kind is InfraTimeoutError:
        return InfraTimeoutError(
            "endpoint sent no reply",
            context=ModelTimeoutErrorContext(
                transport_type=EnumInfraTransportType.HTTP,
                operation="llm_http_call",
                timeout_seconds=90.0,
            ),
        )
    return kind("endpoint said no")


class _FakeHandler:
    """Stands in for the transport: per-base-url behaviour, calls recorded."""

    behaviours: dict[str, Any] = {}
    calls: list[Any] = []

    def __init__(self, _transport: object) -> None:
        pass

    async def handle(self, request: Any) -> _Reply:
        type(self).calls.append(request)
        behaviour = type(self).behaviours[request.base_url]
        if isinstance(behaviour, Exception):
            raise behaviour
        return _Reply()


async def _call(
    tmp_path: Path,
    behaviours: dict[str, Any],
    *,
    fields: str = _OVERFLOW_FIELDS,
    served: bool = True,
) -> tuple[str, list[Any]]:
    roster = load_review_voters(_overlay(tmp_path, fields))
    assert roster.ok, roster.error_message
    adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())
    _FakeHandler.behaviours = behaviours
    _FakeHandler.calls = []
    with (
        patch.dict("os.environ", {"LOCAL_LLM_SHARED_SECRET": "x"}),
        patch(
            "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible",
            _FakeHandler,
        ),
        patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
            return_value="Model-X",
        ),
    ):
        text = await adapter_ai_reviewer.call_model("sys", "usr", model_key="second")
    return text, list(_FakeHandler.calls)


@pytest.mark.asyncio
class TestCall:
    async def test_a_healthy_primary_never_touches_the_overflow(
        self, tmp_path: Path
    ) -> None:
        text, calls = await _call(tmp_path, {_PRIMARY: None, _OVERFLOW: None})

        assert text == "[]"
        assert [c.base_url for c in calls] == [_PRIMARY]
        assert adapter_ai_reviewer.SERVED_BASE_URLS["second"] == _PRIMARY

    @pytest.mark.parametrize(
        "failure",
        [
            InfraUnavailableError,  # 503: the queue is full
            InfraRateLimitedError,  # 429
            InfraConnectionError,  # refused
            InfraTimeoutError,  # no reply within the budget
        ],
    )
    async def test_a_full_or_silent_primary_moves_the_call_to_the_overflow(
        self, tmp_path: Path, failure: type[Exception]
    ) -> None:
        text, calls = await _call(
            tmp_path, {_PRIMARY: _error(failure), _OVERFLOW: None}
        )

        assert text == "[]"
        assert [c.base_url for c in calls] == [_PRIMARY, _OVERFLOW]
        assert adapter_ai_reviewer.SERVED_BASE_URLS["second"] == _OVERFLOW

    async def test_the_primary_gets_one_short_attempt_and_the_last_its_full_budget(
        self, tmp_path: Path
    ) -> None:
        _, calls = await _call(
            tmp_path, {_PRIMARY: _error(InfraUnavailableError), _OVERFLOW: None}
        )

        primary, overflow = calls
        assert primary.timeout_seconds == 90
        assert primary.max_retries == 0
        assert overflow.timeout_seconds == 300
        assert overflow.max_retries == 1
        assert overflow.endpoint_url == f"{_OVERFLOW}/v1/chat/completions"

    async def test_without_overflow_after_seconds_the_primary_keeps_its_timeout(
        self, tmp_path: Path
    ) -> None:
        fields = 'overflow_endpoint_urls: ["http://overflow.example:8000"]\n'
        _, calls = await _call(
            tmp_path,
            {_PRIMARY: _error(InfraUnavailableError), _OVERFLOW: None},
            fields=fields,
        )

        assert calls[0].timeout_seconds == 300
        assert calls[0].max_retries == 0

    async def test_overflow_endpoints_are_tried_in_order(self, tmp_path: Path) -> None:
        fields = f'overflow_endpoint_urls:\n  - "{_OVERFLOW}"\n  - "{_OVERFLOW_2}"\n'
        _, calls = await _call(
            tmp_path,
            {
                _PRIMARY: _error(InfraUnavailableError),
                _OVERFLOW: _error(InfraTimeoutError),
                _OVERFLOW_2: None,
            },
            fields=fields,
        )

        assert [c.base_url for c in calls] == [_PRIMARY, _OVERFLOW, _OVERFLOW_2]
        assert adapter_ai_reviewer.SERVED_BASE_URLS["second"] == _OVERFLOW_2

    async def test_the_last_endpoint_failing_is_the_vote_failing(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(InfraUnavailableError):
            await _call(
                tmp_path,
                {
                    _PRIMARY: _error(InfraUnavailableError),
                    _OVERFLOW: _error(InfraUnavailableError),
                },
            )
        assert "second" not in adapter_ai_reviewer.SERVED_BASE_URLS

    async def test_a_rejected_request_would_fail_the_same_everywhere(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(InfraRequestRejectedError):
            await _call(
                tmp_path,
                {_PRIMARY: _error(InfraRequestRejectedError), _OVERFLOW: None},
            )
        assert [c.base_url for c in _FakeHandler.calls] == [_PRIMARY]

    async def test_a_voter_with_no_overflow_calls_once_with_its_own_budget(
        self, tmp_path: Path
    ) -> None:
        text, calls = await _call(tmp_path, {_PRIMARY: None}, fields="")

        assert text == "[]"
        (only,) = calls
        assert only.timeout_seconds == 300
        assert only.max_retries == 1

    async def test_a_voter_with_no_overflow_does_not_fail_over_on_unavailable(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(InfraUnavailableError):
            await _call(tmp_path, {_PRIMARY: _error(InfraUnavailableError)}, fields="")

    async def test_a_primary_whose_served_model_cannot_be_read_falls_over(
        self, tmp_path: Path
    ) -> None:
        from omniintelligence.review_pairing.served_model_resolver import (
            ServedModelResolutionError,
        )

        def _resolve(base_url: str, **_: object) -> str:
            if base_url == _PRIMARY:
                raise ServedModelResolutionError("connection refused")
            return "Model-X"

        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))
        adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())
        _FakeHandler.behaviours = {_PRIMARY: None, _OVERFLOW: None}
        _FakeHandler.calls = []
        with (
            patch.dict("os.environ", {"LOCAL_LLM_SHARED_SECRET": "x"}),
            patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible",
                _FakeHandler,
            ),
            patch(
                "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
                side_effect=_resolve,
            ),
        ):
            await adapter_ai_reviewer.call_model("sys", "usr", model_key="second")

        assert [c.base_url for c in _FakeHandler.calls] == [_OVERFLOW]


class TestReachability:
    def test_an_unreachable_primary_does_not_drop_a_voter_that_has_overflow(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))
        adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())

        def _tcp(host: str, port: int, *_: object, **__: object) -> bool:
            return host in {"overflow.example", "first.example"}

        with patch.object(adapter_ai_reviewer, "_probe_tcp", side_effect=_tcp):
            reachable = adapter_ai_reviewer.probe_local_reachability(
                ["first", "second"]
            )

        assert reachable == {"first": True, "second": True}

    def test_a_voter_with_no_reachable_endpoint_is_unreachable(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))
        adapter_ai_reviewer.register_review_voters(roster.endpoint_configs())

        with patch.object(adapter_ai_reviewer, "_probe_tcp", return_value=False):
            reachable = adapter_ai_reviewer.probe_local_reachability(["second"])

        assert reachable == {"second": False}


class TestIdentityAndBudget:
    def test_a_vote_is_counted_against_the_host_that_cast_it(
        self, tmp_path: Path
    ) -> None:
        config = load_review_voters(
            _overlay(tmp_path, _OVERFLOW_FIELDS)
        ).endpoint_configs()["second"]

        assert reviewer_identity("second", config, {}) == f"{_PRIMARY}#served"
        assert (
            reviewer_identity("second", config, {}, served_base_url=_OVERFLOW)
            == f"{_OVERFLOW}#served"
        )

    def test_the_budget_counts_the_time_spent_giving_up_on_the_primary(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, _OVERFLOW_FIELDS))
        plain = load_review_voters(_overlay(tmp_path))
        with_overflow = compute_sequential_worst_case(
            ["second"], max_retries=1, configs=roster.endpoint_configs()
        )[0]
        without = compute_sequential_worst_case(
            ["second"], max_retries=1, configs=plain.endpoint_configs()
        )[0]

        assert without.overflow_seconds == 0
        assert with_overflow.overflow_seconds == 90
        assert with_overflow.worst_case_seconds == without.worst_case_seconds + 90
        assert "90s overflow" in format_budget_breakdown([with_overflow])
