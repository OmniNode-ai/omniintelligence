# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for reachability probe and API fallback selection logic.

Covers OMN-8654: hostile_reviewer silent 'passed' when LAN endpoints
unreachable from GitHub Actions cloud runners.

Reference: OMN-8654
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    _API_FALLBACK_KEYS,
    _LOCAL_MODEL_KEYS,
    _PROBE_MAX_ATTEMPTS,
    _PROBE_TIMEOUT_SECONDS,
    _probe_tcp,
    probe_local_reachability,
    select_models_with_fallback,
)


@pytest.mark.unit
class TestProbeTcp:
    def test_unreachable_returns_false(self) -> None:
        # 192.0.2.x is TEST-NET — guaranteed unreachable per RFC 5737.
        # Single attempt keeps this test fast; retry semantics covered below.
        result = _probe_tcp("192.0.2.1", 9999, timeout=0.5, attempts=1)
        assert result is False

    def test_reachable_returns_true(self) -> None:
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda self: self  # noqa: ARG005
            mock_conn.return_value.__exit__ = lambda *_: None
            result = _probe_tcp("127.0.0.1", 80)
        assert result is True

    def test_os_error_returns_false(self) -> None:
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = _probe_tcp("127.0.0.1", 9999, attempts=1)
        assert result is False

    def test_default_threshold_matches_ci_preflight(self) -> None:
        # Regression guard for OMN-14176: the probe must match the CI reviewer
        # preflight threshold (5s x 3 attempts). A 2s single-shot lost the race
        # under GPU load and produced a DEGRADED false-green.
        assert _PROBE_TIMEOUT_SECONDS == 5.0
        assert _PROBE_MAX_ATTEMPTS == 3

    def test_retries_until_success(self) -> None:
        # Two transient failures, then a live connect — a live-but-slow endpoint.
        with (
            patch(
                "socket.create_connection",
                side_effect=[OSError("busy"), OSError("busy"), MagicMock()],
            ) as mock_conn,
            patch(
                "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.time.sleep"
            ) as mock_sleep,
        ):
            result = _probe_tcp("127.0.0.1", 80, attempts=3)
        assert result is True
        assert mock_conn.call_count == 3
        assert mock_sleep.call_count == 2

    def test_exhausts_all_attempts(self) -> None:
        with (
            patch(
                "socket.create_connection", side_effect=OSError("refused")
            ) as mock_conn,
            patch(
                "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.time.sleep"
            ) as mock_sleep,
        ):
            result = _probe_tcp("127.0.0.1", 9999)
        assert result is False
        assert mock_conn.call_count == _PROBE_MAX_ATTEMPTS
        # Sleep only between attempts, never after the final failure.
        assert mock_sleep.call_count == _PROBE_MAX_ATTEMPTS - 1


@pytest.mark.unit
class TestProbeLocalReachability:
    def test_skips_non_local_keys(self) -> None:
        result = probe_local_reachability(["codex"])
        assert "codex" not in result

    def test_skips_api_fallback_keys(self) -> None:
        for key in _API_FALLBACK_KEYS:
            result = probe_local_reachability([key])
            assert key not in result

    def test_all_local_unreachable(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=False,
        ):
            result = probe_local_reachability(["deepseek-r1", "qwen3-coder"])
        assert result == {"deepseek-r1": False, "qwen3-coder": False}

    def test_all_local_reachable(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=True,
        ):
            result = probe_local_reachability(["deepseek-r1", "qwen3-coder"])
        assert result == {"deepseek-r1": True, "qwen3-coder": True}

    def test_partial_reachability(self) -> None:
        def side_effect(host: str, port: int, **kwargs: object) -> bool:
            return host == "192.168.86.200"

        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            side_effect=side_effect,
        ):
            result = probe_local_reachability(["deepseek-r1", "qwen3-coder"])
        # qwen3-coder defaults to 192.168.86.201 — unreachable in this scenario
        assert result["qwen3-coder"] is False

    def test_unknown_model_key_skipped(self) -> None:
        result = probe_local_reachability(["nonexistent-model"])
        assert "nonexistent-model" not in result


@pytest.mark.unit
class TestSelectModelsWithFallback:
    def test_all_local_unreachable_activates_api_fallback(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=False,
        ):
            models, skipped = select_models_with_fallback(
                ["deepseek-r1", "qwen3-coder"]
            )

        assert "codex" in models
        assert "deepseek-r1" in skipped
        assert "qwen3-coder" in skipped
        assert "deepseek-r1" not in models
        assert "qwen3-coder" not in models

    def test_partial_local_reachable_runs_reachable_only(self) -> None:
        # Patch probe_local_reachability directly so this test is independent of
        # env-var URL overrides that change which host:port gets probed.
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.probe_local_reachability",
            return_value={"deepseek-r1": True, "qwen3-next": False},
        ):
            models, skipped = select_models_with_fallback(["deepseek-r1", "qwen3-next"])

        assert "deepseek-r1" in models
        assert "qwen3-next" in skipped
        assert "codex" not in models

    def test_all_local_reachable_no_fallback(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=True,
        ):
            models, skipped = select_models_with_fallback(
                ["deepseek-r1", "qwen3-coder"]
            )

        assert set(models) == {"deepseek-r1", "qwen3-coder"}
        assert skipped == []
        assert "codex" not in models

    def test_non_local_keys_pass_through_unchanged(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=False,
        ):
            models, skipped = select_models_with_fallback(["codex"])

        assert "codex" in models
        assert skipped == []

    def test_mixed_local_and_non_local_all_local_unreachable(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer._probe_tcp",
            return_value=False,
        ):
            models, skipped = select_models_with_fallback(["codex", "deepseek-r1"])

        assert models.count("codex") == 1
        assert "deepseek-r1" in skipped

    def test_no_local_models_requested_no_probe_called(self) -> None:
        with patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.probe_local_reachability"
        ) as mock_probe:
            models, skipped = select_models_with_fallback(["codex"])

        mock_probe.assert_not_called()
        assert models == ["codex"]
        assert skipped == []

    def test_local_model_keys_constants(self) -> None:
        assert "deepseek-r1" in _LOCAL_MODEL_KEYS
        assert "qwen3-coder" in _LOCAL_MODEL_KEYS
        assert "qwen3-14b" in _LOCAL_MODEL_KEYS
        assert "codex" not in _LOCAL_MODEL_KEYS
