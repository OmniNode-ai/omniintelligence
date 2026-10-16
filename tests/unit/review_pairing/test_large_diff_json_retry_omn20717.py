# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A large diff still yields review JSON from a voter that answers in prose (OMN-20717).

On omnimarket#3989 (26 files, about 93 KB of diff) and omnimarket#4002 the
``correctness`` voter replied with free text twice (15895 then 32638 chars):
"reply did not parse ... retrying once with max_tokens=8192", then
"unparseable reply: no review JSON in 2 attempt(s)". The retry resent the same
prompt, so the model reasoned in prose again until the token cap, and the gate
read degraded_quorum with 0 findings.

The retry is now JSON-only: the prompt ends with a strict JSON instruction and
the schema, the request carries the findings ``response_format`` whatever the
voter's own setting, and the output budget grows with the diff. A diff that
still does not answer is reviewed in file chunks and the findings are merged.
A voter that never produces JSON still fails its vote; a prose reply is never a
pass and the two-model quorum is untouched.

``free_text_reply_omn20717.txt`` is a 15895-char free-text reply of the shape
the gate logged. The original reply was never saved (the gate logs lengths, not
text, to keep private diffs out of CI logs), so this one is a reconstruction
with the logged length.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    json_retry_max_tokens,
    split_diff_into_file_chunks,
    try_parse_review_response,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "free_text_reply_omn20717.txt"
_PROSE = _FIXTURE.read_text().rstrip("\n")


def _finding(title: str, location: str = "a.py") -> dict[str, str]:
    return {
        "category": "correctness",
        "severity": "major",
        "title": title,
        "description": "The loop skips the last item.",
        "evidence": "line 3",
        "proposed_fix": "use <=",
        "location": location,
    }


def _file_diff(name: str, body_chars: int) -> str:
    body = "".join(f"+line {i} of {name}\n" for i in range(body_chars // 20))
    return (
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n@@ -0,0 +1 @@\n"
        f"{body}"
    )


def _big_diff(files: int = 6, chars_per_file: int = 16_000) -> str:
    return "".join(_file_diff(f"src/f{i}.py", chars_per_file) for i in range(files))


@pytest.mark.unit
class TestFixture:
    def test_the_saved_reply_is_free_text_of_the_logged_length(self) -> None:
        assert len(_PROSE) == 15895
        assert try_parse_review_response(_PROSE) is None


@pytest.mark.unit
class TestJsonOnlyRetry:
    @pytest.mark.asyncio
    async def test_a_prose_reply_is_retried_json_only_and_yields_findings(self) -> None:
        diff = _big_diff()
        valid = json.dumps([_finding("Off by one")])
        call = AsyncMock(side_effect=[_PROSE, valid])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                diff, model="qwen3-review", review_type="pr"
            )

        assert result.success is True
        assert result.result_count == 1
        assert result.parse_failed is False
        first, retry = call.await_args_list
        # The first call is unchanged.
        assert "force_findings_schema" not in first.kwargs
        assert "RESPONSE FORMAT" not in first.args[1]
        # The retry is JSON-only: a strict instruction with the schema, and the
        # constrained-decoding request, not the same prompt again.
        assert "RESPONSE FORMAT" in retry.args[1]
        assert '"proposed_fix"' in retry.args[1]
        assert retry.args[1].startswith(first.args[1])
        assert retry.kwargs["force_findings_schema"] is True
        assert retry.kwargs["max_tokens"] == json_retry_max_tokens(len(diff))
        assert first.kwargs["model_key"] == retry.kwargs["model_key"]

    @pytest.mark.asyncio
    async def test_a_clean_json_only_retry_is_a_clean_review(self) -> None:
        call = AsyncMock(side_effect=[_PROSE, "[]"])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                _big_diff(), model="qwen3-review", review_type="pr"
            )

        assert call.await_count == 2
        assert result.success is True
        assert result.result_count == 0

    @pytest.mark.asyncio
    async def test_a_rejected_response_format_falls_back_to_the_instruction(
        self,
    ) -> None:
        valid = json.dumps([_finding("Off by one")])
        call = AsyncMock(side_effect=[_PROSE, RuntimeError("400 bad format"), valid])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                _big_diff(), model="qwen3-review", review_type="pr"
            )

        assert result.success is True
        assert result.result_count == 1
        _, constrained, instruction_only = call.await_args_list
        assert constrained.kwargs["force_findings_schema"] is True
        assert "force_findings_schema" not in instruction_only.kwargs
        assert "RESPONSE FORMAT" in instruction_only.args[1]


@pytest.mark.unit
class TestOutputBudget:
    def test_budget_grows_with_the_diff_and_is_bounded(self) -> None:
        small = json_retry_max_tokens(1_000)
        large = json_retry_max_tokens(93_000)
        huge = json_retry_max_tokens(10_000_000)
        assert small == adapter_ai_reviewer._RETRY_MAX_TOKENS
        assert large > small
        assert huge == adapter_ai_reviewer._JSON_RETRY_MAX_TOKENS_CAP


@pytest.mark.unit
class TestFileChunks:
    def test_a_small_diff_is_one_chunk(self) -> None:
        assert len(split_diff_into_file_chunks(_big_diff(2, 2_000), 48_000)) == 1

    def test_a_plan_with_no_file_headers_is_one_chunk(self) -> None:
        assert split_diff_into_file_chunks("# Plan\n" * 20_000, 1_000) == [
            "# Plan\n" * 20_000
        ]

    def test_chunks_cut_at_file_boundaries_and_lose_nothing(self) -> None:
        diff = _big_diff(6, 16_000)
        chunks = split_diff_into_file_chunks(diff, 48_000)
        assert len(chunks) > 1
        assert "".join(chunks) == diff
        assert all(c.startswith("diff --git ") for c in chunks)
        assert all(len(c) <= 48_000 + 16_100 for c in chunks)

    def test_one_file_larger_than_the_target_stays_whole(self) -> None:
        diff = _file_diff("big.py", 100_000) + _file_diff("small.py", 100)
        chunks = split_diff_into_file_chunks(diff, 48_000)
        assert len(chunks) == 2
        assert chunks[0].startswith("diff --git a/big.py")


@pytest.mark.unit
class TestChunkedReview:
    @pytest.mark.asyncio
    async def test_a_voter_that_answers_chunks_but_not_the_whole_diff_votes(
        self,
    ) -> None:
        diff = _big_diff(6, 16_000)
        n_chunks = len(split_diff_into_file_chunks(diff, 48_000))
        assert n_chunks > 1
        chunk_replies = [
            json.dumps([_finding(f"Bug in chunk {i}")]) for i in range(n_chunks)
        ]
        # Whole diff: prose. JSON-only retry on the whole diff: prose. Then one
        # JSON-only call per chunk.
        call = AsyncMock(side_effect=[_PROSE, _PROSE, *chunk_replies])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                diff, model="qwen3-review", review_type="pr"
            )

        assert result.success is True
        assert result.parse_failed is False
        assert result.result_count == n_chunks
        chunk_calls = call.await_args_list[2:]
        assert len(chunk_calls) == n_chunks
        for chunk_call in chunk_calls:
            assert "RESPONSE FORMAT" in chunk_call.args[1]
            assert chunk_call.kwargs["force_findings_schema"] is True
            # Each call carries a slice of the diff, not all of it.
            assert len(chunk_call.args[1]) < len(diff)
            assert "chunk" in chunk_call.args[1]

    @pytest.mark.asyncio
    async def test_duplicate_findings_across_chunks_are_merged(self) -> None:
        diff = _big_diff(6, 16_000)
        n_chunks = len(split_diff_into_file_chunks(diff, 48_000))
        same = json.dumps([_finding("Shared defect", "src/f0.py")])
        call = AsyncMock(side_effect=[_PROSE, _PROSE, *([same] * n_chunks)])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                diff, model="qwen3-review", review_type="pr"
            )

        assert result.success is True
        assert result.result_count == 1

    @pytest.mark.asyncio
    async def test_one_prose_chunk_fails_the_whole_vote(self) -> None:
        diff = _big_diff(6, 16_000)
        n_chunks = len(split_diff_into_file_chunks(diff, 48_000))
        ok = json.dumps([_finding("Bug")])
        replies = [ok] * (n_chunks - 1) + [_PROSE]
        call = AsyncMock(side_effect=[_PROSE, _PROSE, *replies])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                diff, model="qwen3-review", review_type="pr"
            )

        assert result.success is False
        assert result.parse_failed is True
        assert result.findings == []
        assert result.error is not None
        assert "unparseable" in result.error

    @pytest.mark.asyncio
    async def test_a_prose_reply_to_every_call_still_fails_loud(self) -> None:
        call = AsyncMock(return_value=_PROSE)
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                _big_diff(), model="qwen3-review", review_type="pr"
            )

        assert result.success is False
        assert result.parse_failed is True
        assert result.findings == []
        assert result.raw_reply_length == len(_PROSE)
        assert _PROSE[:60] not in result.model_dump_json()
        # Whole diff twice, then the first chunk fails the vote: no more calls.
        assert call.await_count == 3

    @pytest.mark.asyncio
    async def test_a_single_file_diff_is_not_chunked(self) -> None:
        call = AsyncMock(return_value=_PROSE)
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                _file_diff("one.py", 5_000), model="qwen3-review", review_type="pr"
            )

        assert call.await_count == 2
        assert result.success is False
        assert result.parse_failed is True


@pytest.mark.unit
class TestForcedResponseFormat:
    def test_forcing_adds_the_findings_schema_to_any_voter(self) -> None:
        config = adapter_ai_reviewer.MODEL_REGISTRY["qwen3-review"]
        assert config.constrain_findings_schema is False
        assert "response_format" not in adapter_ai_reviewer._build_extra_body(config)
        forced = adapter_ai_reviewer._build_extra_body(
            config, force_findings_schema=True
        )
        assert forced["response_format"] == adapter_ai_reviewer.FINDINGS_RESPONSE_FORMAT

    @pytest.mark.asyncio
    async def test_call_model_sends_response_format_only_when_forced(self) -> None:
        env = dict.fromkeys(("LOCAL_LLM_SHARED_SECRET",), "x")
        env["LLM_QWEN3_REVIEW_URL"] = "http://x:1"
        with patch.dict("os.environ", env, clear=False):
            with (
                patch(
                    "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
                ) as handler_cls,
                patch(
                    "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
                    return_value="served-model-id",
                ),
            ):
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-review"
                )
                plain = handler_inst.handle.call_args[0][0]
                await adapter_ai_reviewer.call_model(
                    "sys",
                    "usr",
                    model_key="qwen3-review",
                    force_findings_schema=True,
                )
                forced = handler_inst.handle.call_args[0][0]

        assert "response_format" not in plain.extra_body
        assert (
            forced.extra_body["response_format"]
            == adapter_ai_reviewer.FINDINGS_RESPONSE_FORMAT
        )
