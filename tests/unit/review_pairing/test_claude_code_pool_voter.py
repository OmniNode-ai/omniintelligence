# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Claude Code review voters use the host account pool (OMN-20910)."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from omniintelligence.handlers import (
    handler_claude_code_review_host as handler,
)
from omniintelligence.nodes.node_claude_code_review_effect.handlers import (
    handler_claude_code_review as effect_handler,
)
from omniintelligence.nodes.node_claude_code_review_effect.handlers.handler_claude_code_review import (
    POOL_MODULE,
    HandlerClaudeCodeReview,
)
from omniintelligence.nodes.node_claude_code_review_effect.models.model_claude_code_review import (
    ModelClaudeCodeReviewRequest,
    ModelClaudeCodeReviewResult,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.handlers.handler_review_voters_overlay import (
    probe_target_lines,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer as adapter
from omniintelligence.review_pairing.cli_review import (
    _select_overlay_voters,
    main,
    run_review,
)
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.retry_budget import compute_sequential_worst_case
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contract_bound_handler_injects_host_configuration(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    contract_path = (
        Path(handler.__file__).parents[1]
        / "nodes/node_claude_code_review_effect/contract.yaml"
    )
    contract = yaml.safe_load(contract_path.read_text())
    binding = contract["handler_routing"]["handlers"][0]["handler"]
    bound_handler = getattr(
        importlib.import_module(binding["module"]), binding["class"]
    )
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/contract-pool-python")
    monkeypatch.setenv("PATH", "/fake/claude-bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-key-must-not-reach-effect")
    response = ModelClaudeCodeReviewResult(
        correlation_id=request_model.correlation_id, success=True, response="[]"
    )
    invoke = AsyncMock(return_value=response)
    constructed: list[dict[str, object]] = []

    class RecordingReview(HandlerClaudeCodeReview):
        def __init__(self, **kwargs: object) -> None:
            constructed.append(kwargs)

        handle = invoke

    monkeypatch.setattr(effect_handler, "HandlerClaudeCodeReview", RecordingReview)

    assert await bound_handler().handle(request_model) is response
    invoke.assert_awaited_once()
    assert invoke.await_args.args == (request_model,)
    assert len(constructed) == 1
    assert constructed[0]["pool_python"] == "/fake/contract-pool-python"
    environment = constructed[0]["environment"]
    assert environment["PATH"] == "/fake/claude-bin"
    assert "ANTHROPIC_API_KEY" not in environment


class FakeProcess:
    def __init__(self, code: int, stdout: str, stderr: str = "") -> None:
        self.returncode = code
        self.stdout = stdout.encode()
        self.stderr = stderr.encode()

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr


@pytest.fixture
def request_model() -> ModelClaudeCodeReviewRequest:
    return ModelClaudeCodeReviewRequest(
        model="claude-sonnet-5-5",
        system_prompt="Review carefully.",
        user_prompt="diff",
        timeout_seconds=30,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_usage_limit_marks_account_and_rotates_without_logging_token(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    first, second = "fixture-account-one-secret", "fixture-account-two-secret"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-token-must-not-win")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-api-key-must-not-win")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://untrusted.invalid")
    replies = iter(
        [
            FakeProcess(
                0, first, "claude-pool host=host tokens=2 limited=0 label=acct-a"
            ),
            FakeProcess(
                1,
                json.dumps({"is_error": True, "result": "You've hit your limit"}),
                first,
            ),
            FakeProcess(0, "claude-pool host=host tokens=2 limited=1 label=acct-b"),
            FakeProcess(
                0, second, "claude-pool host=host tokens=2 limited=1 label=acct-b"
            ),
            FakeProcess(
                0,
                json.dumps(
                    {
                        "is_error": False,
                        "result": "[]",
                        "usage": {"input_tokens": 9, "output_tokens": 2},
                    }
                ),
            ),
        ]
    )
    calls: list[tuple[tuple[str, ...], dict]] = []

    async def spawn(*argv: str, **kwargs: object) -> FakeProcess:
        calls.append((argv, kwargs))
        return next(replies)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.success and result.response == "[]"
    assert result.correlation_id == request_model.correlation_id
    assert (result.input_tokens, result.output_tokens) == (9, 2)
    assert calls[0][0] == ("/fake/pool-python", "-m", POOL_MODULE, "resolve")
    assert calls[2][0][-5:] == (
        "mark-limited",
        "--label",
        "acct-a",
        "--seconds",
        "3600",
    )
    for index, token in [(1, first), (4, second)]:
        argv, kwargs = calls[index]
        assert argv[0:2] == ("claude", "-p")
        assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"
        assert argv[argv.index("--tools") + 1] == ""
        assert "--no-session-persistence" in argv
        assert "--strict-mcp-config" in argv
        env = kwargs["env"]
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == token
        assert "ANTHROPIC_API_KEY" not in env
        assert "ANTHROPIC_BASE_URL" not in env
        assert token not in " ".join(argv)
    for token in (first, second):
        assert token not in caplog.text + result.model_dump_json()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_limited_fails_closed_without_running_claude(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    spawn = AsyncMock(return_value=FakeProcess(4, "", "ALARM every token limited"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert not result.success and result.error == "claude_pool_all_limited"
    assert result.response == ""
    assert spawn.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_errors_never_expose_pool_or_claude_output(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    fixture_value = "fixture-private-account-token"
    replies = iter(
        [
            FakeProcess(
                0,
                fixture_value,
                "claude-pool host=host tokens=1 limited=0 label=acct-a",
            ),
            FakeProcess(1, fixture_value, f"authentication failed {fixture_value}"),
        ]
    )
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=lambda *_a, **_kw: next(replies)),
    )
    result = await handler.handle(request_model)
    assert result.error == "claude_code_failed"
    assert fixture_value not in caplog.text + result.model_dump_json()


@pytest.fixture(autouse=True)
def restore_registry():
    registry, local = dict(adapter.MODEL_REGISTRY), adapter._LOCAL_MODEL_KEYS
    yield
    adapter.MODEL_REGISTRY.clear()
    adapter.MODEL_REGISTRY.update(registry)
    adapter._LOCAL_MODEL_KEYS = local


def overlay(tmp_path: Path, **overrides: object) -> Path:
    voters = []
    for role, model in [
        ("correctness", "claude-sonnet-5-5"),
        ("security", "claude-opus-5-5"),
    ]:
        voters.append(
            {
                "voter_id": role,
                "provider": "claude_code",
                "model": model,
                "required": True,
                "timeout_seconds": 30,
                "review_focus": "Inspect contracts.",
            }
        )
    voters[0].update(overrides)
    path = tmp_path / "voters.yaml"
    path.write_text(
        yaml.safe_dump({"schema_version": "review_voters_overlay.v1", "voters": voters})
    )
    return path


@pytest.mark.unit
def test_overlay_selects_models_without_api_keys_endpoints_or_lab_probes(
    tmp_path: Path,
) -> None:
    roster = load_review_voters(overlay(tmp_path))
    assert roster.ok, roster.error_message
    assert probe_target_lines(roster) == []
    configs = roster.endpoint_configs()
    adapter.register_review_voters(configs)
    with patch.object(
        adapter, "_probe_url", side_effect=AssertionError("No lab calls")
    ):
        assert _select_overlay_voters(roster) == (["correctness", "security"], [])
    assert [config.api_model_id for config in configs.values()] == [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]
    assert all(
        config.api_key_env is None and config.default_url == ""
        for config in configs.values()
    )
    assert all("provider claude_code" in voter.describe() for voter in roster.voters)
    budgets = compute_sequential_worst_case(roster.voter_ids, configs=configs)
    assert sum(b.worst_case_seconds for b in budgets) == 60
    assert all(b.total_attempts == 1 for b in budgets)
    swapped = load_review_voters(
        overlay(tmp_path, model="claude-opus-5-5")
    ).endpoint_configs()
    assert swapped["correctness"].api_model_id == "claude-opus-5-5"
    assert reviewer_identity(
        "correctness", swapped["correctness"], {}
    ) == reviewer_identity("security", configs["security"], {})
    assert reviewer_identity(
        "correctness", configs["correctness"], {}
    ) != reviewer_identity("security", configs["security"], {})


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid",
    [
        {"api_key_env": "_".join(("UNUSED", "KEY"))},
        {"endpoint_url": "https://example.invalid"},
        {"temperature": 0.4},
        {"top_p": 0.8},
        {"max_retries": 1},
        {"model": ""},
        {"model_id_source": "served"},
    ],
)
def test_overlay_refuses_unsupported_options_naming_voter(
    tmp_path: Path, invalid: dict
) -> None:
    roster = load_review_voters(overlay(tmp_path, **invalid))
    assert not roster.ok and roster.error_voter_id == "correctness"


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "limit_message",
    [
        "You've hit your weekly limit",
        "Usage limit exceeded",
        "Rate limit reached",
        "rate_limit_error",
        "You're out of extra usage",
    ],
)
async def test_final_limited_account_fails_closed_after_mark(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
    limit_message: str,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    replies = iter(
        [
            FakeProcess(
                0, "fake-token", "claude-pool host=h tokens=1 limited=0 label=acct-a"
            ),
            FakeProcess(
                1,
                json.dumps({"is_error": True, "result": limit_message}),
            ),
            FakeProcess(4, "ALARM every token limited"),
        ]
    )
    spawn = AsyncMock(side_effect=lambda *_a, **_kw: next(replies))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.error == "claude_pool_all_limited"
    assert spawn.await_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_timeout_kills_and_reaps_claude(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=TimeoutError("secret-diagnostic"))
    process.wait = AsyncMock(return_value=-9)
    spawn = AsyncMock(
        side_effect=[
            FakeProcess(
                0, "fake-token", "claude-pool host=h tokens=1 limited=0 label=acct-a"
            ),
            process,
        ]
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.error == "claude_code_timeout"
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
    assert "secret-diagnostic" not in result.model_dump_json()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_pool_never_uses_ambient_token_or_login(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.delenv("ONEX_CLAUDE_POOL_PY", raising=False)
    monkeypatch.delenv("OMNI_HOME", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "wrong-token")
    spawn = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.error == "claude_pool_unavailable"
    spawn.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mark_code, expected",
    [
        (1, "claude_pool_mark_failed"),
        (0, "claude_pool_rotation_stalled"),
    ],
)
async def test_rotation_fails_closed_when_pool_cannot_advance(
    monkeypatch: pytest.MonkeyPatch,
    request_model: ModelClaudeCodeReviewRequest,
    mark_code: int,
    expected: str,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    resolved = FakeProcess(
        0, "fake-token", "claude-pool host=h tokens=1 limited=0 label=acct-a"
    )
    replies = iter(
        [
            resolved,
            FakeProcess(
                1, json.dumps({"is_error": True, "result": "You've hit your limit"})
            ),
            FakeProcess(mark_code, "raw-private-diagnostic"),
            resolved,
        ]
    )
    spawn = AsyncMock(side_effect=lambda *_a, **_kw: next(replies))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.error == expected
    assert spawn.await_count == (3 if mark_code else 4)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_result_redacts_token_echo_and_does_not_rotate_on_prose(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    fixture_value = "fixture-secret-value"
    replies = iter(
        [
            FakeProcess(
                0, fixture_value, "claude-pool host=h tokens=1 limited=0 label=acct-a"
            ),
            FakeProcess(
                0,
                json.dumps(
                    {
                        "is_error": False,
                        "result": "You've hit your limit " + fixture_value,
                    }
                ),
            ),
        ]
    )
    spawn = AsyncMock(side_effect=lambda *_a, **_kw: next(replies))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await handler.handle(request_model)
    assert result.success and result.response.endswith("[REDACTED]")
    assert fixture_value not in result.model_dump_json() + caplog.text
    assert spawn.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_excluded_repository_refused_before_pool_access(tmp_path: Path) -> None:
    roster = load_review_voters(
        overlay(tmp_path, excluded_repositories=["private-repo"])
    )
    assert roster.ok, roster.error_message
    adapter.register_review_voters(roster.endpoint_configs())
    with patch.object(handler, "handle", AsyncMock()) as invoke:
        result = await adapter.async_parse_raw(
            "private diff", model="correctness", repository="org/private-repo"
        )
    assert not result.success and "forbidden" in result.error
    invoke.assert_not_called()


@pytest.mark.unit
def test_cli_reports_all_limited_required_voters_without_lab_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", "/fake/pool-python")
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", AsyncMock(return_value=FakeProcess(4, ""))
    )
    plan = tmp_path / "plan.md"
    plan.write_text("# Review this change")
    with patch.object(
        adapter, "_probe_url", side_effect=AssertionError("No lab fallback")
    ):
        assert (
            main(["--file", str(plan), "--voters-overlay", str(overlay(tmp_path))]) == 2
        )
    captured = capsys.readouterr()
    assert "required review voter 'correctness' did not vote" in captured.err
    assert "required review voter 'security' did not vote" in captured.err
    assert "claude_pool_all_limited" in captured.err
    result = json.loads(captured.out)
    assert result["models_succeeded"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_subprocess_adapter_uses_stdin_model_and_pool_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # These executables are doubles for the pool node and Claude, not credentials.
    pool = tmp_path / "pool-python"
    pool.write_text(
        f"#!{sys.executable}\n"
        """import sys
assert sys.argv[1:] == ["-m", "omnimarket.nodes.node_claude_token_pool_effect", "resolve"]
print("fixture-pool-value", end="")
print("claude-pool host=test tokens=1 limited=0 label=acct-a", file=sys.stderr)
"""
    )
    pool.chmod(0o755)
    claude = tmp_path / "claude"
    claude.write_text(
        f"#!{sys.executable}\n"
        """import json, os, sys
assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "fixture-pool-value"
assert "ANTHROPIC_API_KEY" not in os.environ
assert "Inspect contracts." in sys.argv[sys.argv.index("--system-prompt") + 1]
assert "diff for review" in sys.stdin.read()
model = sys.argv[sys.argv.index("--model") + 1]
assert model in {"claude-sonnet-5-5", "claude-opus-5-5"}
print(json.dumps({"is_error":False, "result":"[]", "usage":{"input_tokens":12,"output_tokens":2}}))
"""
    )
    claude.chmod(0o755)
    monkeypatch.setenv("ONEX_CLAUDE_POOL_PY", str(pool))
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.defpath)
    roster = load_review_voters(overlay(tmp_path))
    adapter.register_review_voters(roster.endpoint_configs())
    result = await run_review("diff for review", roster.voter_ids, review_type="pr")
    assert result.models_succeeded == ["correctness", "security"], (
        result.model_dump_json()
    )
    assert [(r.input_tokens, r.output_tokens) for r in result.results] == [
        (12, 2),
        (12, 2),
    ]
    assert "fixture-pool-value" not in result.model_dump_json()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bus_dispatch_uses_same_handler_and_publishes_correlated_result(
    request_model: ModelClaudeCodeReviewRequest,
) -> None:
    from omnibase_core.models.core.model_envelope_metadata import ModelEnvelopeMetadata
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    from omniintelligence.runtime.contract_topics import (
        canonical_topic_to_dispatch_alias,
        collect_subscribe_topics_from_contracts,
    )
    from omniintelligence.runtime.dispatch_handlers import (
        create_intelligence_dispatch_engine,
    )
    from omniintelligence.topics import IntelligenceCommandTopic, IntentTopic

    producer = MagicMock(publish=AsyncMock())
    engine = create_intelligence_dispatch_engine(
        repository=MagicMock(),
        idempotency_store=MagicMock(),
        intent_classifier=MagicMock(),
        kafka_producer=producer,
    )
    response = ModelClaudeCodeReviewResult(
        correlation_id=request_model.correlation_id, success=True, response="[]"
    )
    envelope = ModelEventEnvelope(
        payload=request_model.model_dump(mode="json"),
        correlation_id=request_model.correlation_id,
        metadata=ModelEnvelopeMetadata(tags={"message_category": "command"}),
    )
    assert (
        IntelligenceCommandTopic.CLAUDE_CODE_REVIEW
        in collect_subscribe_topics_from_contracts()
    )
    with patch.object(handler, "handle", AsyncMock(return_value=response)) as invoke:
        result = await engine.dispatch(
            topic=canonical_topic_to_dispatch_alias(
                IntelligenceCommandTopic.CLAUDE_CODE_REVIEW
            ),
            envelope=envelope,
        )
    assert result.is_successful(), result.error_message
    assert invoke.await_args.args[0] == request_model
    producer.publish.assert_awaited_once_with(
        topic=IntentTopic.CLAUDE_CODE_REVIEW_COMPLETED.value,
        key=str(request_model.correlation_id),
        value=response.model_dump(mode="json"),
    )
