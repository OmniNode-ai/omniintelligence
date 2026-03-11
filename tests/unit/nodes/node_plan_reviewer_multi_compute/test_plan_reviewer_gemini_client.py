# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for PlanReviewerGeminiClient.

All tests use mocked httpx responses — no real network calls.

Ticket: OMN-3286
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from omniintelligence.clients.plan_reviewer_gemini_client import (
    ModelPlanReviewerGeminiConfig,
    PlanReviewerGeminiAuthError,
    PlanReviewerGeminiClient,
    PlanReviewerGeminiClientError,
    PlanReviewerGeminiTimeoutError,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_KEY = "test-gemini-api-key"  # pragma: allowlist secret
_MESSAGES = [{"role": "user", "content": "Review this plan."}]


def _make_config(**kwargs: Any) -> ModelPlanReviewerGeminiConfig:
    defaults: dict[str, Any] = {"api_key": _API_KEY}
    return ModelPlanReviewerGeminiConfig(**{**defaults, **kwargs})


def _make_ok_response(content: str = "Looks good.") -> MagicMock:
    """Return a mock httpx.Response with a successful OpenAI-compat payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    mock_resp.text = json.dumps(mock_resp.json.return_value)
    return mock_resp


def _make_error_response(status_code: int, body: str = "error") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = body
    mock_resp.json.return_value = {}
    return mock_resp


def _patch_client(mock_post: Any, aclose: Any = None) -> Any:
    """Return a patcher context for httpx.AsyncClient in the gemini module."""
    return patch(
        "omniintelligence.clients.plan_reviewer_gemini_client.httpx.AsyncClient",
        return_value=MagicMock(
            post=mock_post,
            aclose=aclose or AsyncMock(),
        ),
    )


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestModelPlanReviewerGeminiConfig:
    """Config model validation."""

    def test_defaults(self) -> None:
        """Config uses sensible defaults."""
        config = _make_config()
        assert config.api_key == _API_KEY
        assert config.model == "gemini-2.0-flash"
        assert "generativelanguage.googleapis.com" in config.chat_url
        assert config.timeout_seconds == 60.0
        assert config.max_tokens == 2048
        assert config.temperature == 0.1

    def test_frozen(self) -> None:
        """Config is immutable (frozen Pydantic model)."""
        config = _make_config()
        with pytest.raises(ValidationError):
            config.api_key = "other"  # type: ignore[misc]

    def test_custom_url_and_model(self) -> None:
        """Custom chat_url and model are accepted."""
        config = _make_config(
            chat_url="https://custom.example.com/chat",
            model="gemini-2.0-flash-exp",
        )
        assert config.chat_url == "https://custom.example.com/chat"
        assert config.model == "gemini-2.0-flash-exp"

    def test_extra_fields_ignored(self) -> None:
        """Extra fields are silently ignored (extra='ignore')."""
        config = ModelPlanReviewerGeminiConfig(
            api_key=_API_KEY,
            unknown_field="ignored",  # type: ignore[call-arg]
        )
        assert config.api_key == _API_KEY


# ---------------------------------------------------------------------------
# Client lifecycle tests
# ---------------------------------------------------------------------------


class TestPlanReviewerGeminiClientLifecycle:
    """Test connect/close/context-manager lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_creates_http_client(self) -> None:
        """connect() creates an httpx.AsyncClient."""
        config = _make_config()
        client = PlanReviewerGeminiClient(config)
        assert not client.is_connected
        await client.connect()
        assert client.is_connected
        await client.close()

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self) -> None:
        """Calling connect() twice does not raise."""
        config = _make_config()
        client = PlanReviewerGeminiClient(config)
        await client.connect()
        await client.connect()  # Should not raise
        assert client.is_connected
        await client.close()

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self) -> None:
        """Calling close() twice does not raise."""
        config = _make_config()
        client = PlanReviewerGeminiClient(config)
        await client.connect()
        await client.close()
        await client.close()  # Should not raise
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Context manager connects and closes automatically."""
        config = _make_config()
        async with PlanReviewerGeminiClient(config) as client:
            assert client.is_connected
        assert not client.is_connected

    def test_config_property(self) -> None:
        """config property returns the injected config."""
        config = _make_config()
        client = PlanReviewerGeminiClient(config)
        assert client.config is config


# ---------------------------------------------------------------------------
# chat() success path
# ---------------------------------------------------------------------------


class TestPlanReviewerGeminiClientChatSuccess:
    """Test the happy path for chat()."""

    @pytest.mark.asyncio
    async def test_chat_returns_content(self) -> None:
        """chat() returns the assistant content string."""
        config = _make_config()
        mock_resp = _make_ok_response("Plan looks solid.")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                result = await client.chat(_MESSAGES)

        assert result == "Plan looks solid."

    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self) -> None:
        """chat() sends model, messages, max_tokens, temperature."""
        config = _make_config(max_tokens=512, temperature=0.0)
        mock_resp = _make_ok_response()
        captured_payload: dict[str, Any] = {}

        async def _spy_post(_url: str, **kwargs: Any) -> MagicMock:
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with _patch_client(_spy_post):
            async with PlanReviewerGeminiClient(config) as client:
                await client.chat(_MESSAGES)

        assert captured_payload["model"] == "gemini-2.0-flash"
        assert captured_payload["messages"] == _MESSAGES
        assert captured_payload["max_tokens"] == 512
        assert captured_payload["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_chat_sends_bearer_auth_header(self) -> None:
        """chat() sends Authorization: Bearer <api_key>."""
        config = _make_config()
        mock_resp = _make_ok_response()
        captured_headers: dict[str, str] = {}

        async def _spy_post(_url: str, **kwargs: Any) -> MagicMock:
            captured_headers.update(kwargs.get("headers", {}))
            return mock_resp

        with _patch_client(_spy_post):
            async with PlanReviewerGeminiClient(config) as client:
                await client.chat(_MESSAGES)

        assert captured_headers["Authorization"] == f"Bearer {_API_KEY}"
        assert captured_headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_chat_max_tokens_override(self) -> None:
        """chat() max_tokens kwarg overrides config value."""
        config = _make_config(max_tokens=2048)
        mock_resp = _make_ok_response()
        captured_payload: dict[str, Any] = {}

        async def _spy_post(_url: str, **kwargs: Any) -> MagicMock:
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with _patch_client(_spy_post):
            async with PlanReviewerGeminiClient(config) as client:
                await client.chat(_MESSAGES, max_tokens=128)

        assert captured_payload["max_tokens"] == 128

    @pytest.mark.asyncio
    async def test_chat_temperature_override(self) -> None:
        """chat() temperature kwarg overrides config value."""
        config = _make_config(temperature=0.1)
        mock_resp = _make_ok_response()
        captured_payload: dict[str, Any] = {}

        async def _spy_post(_url: str, **kwargs: Any) -> MagicMock:
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with _patch_client(_spy_post):
            async with PlanReviewerGeminiClient(config) as client:
                await client.chat(_MESSAGES, temperature=0.8)

        assert captured_payload["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_chat_auto_connects_if_not_connected(self) -> None:
        """chat() connects automatically if called without prior connect()."""
        config = _make_config()
        mock_resp = _make_ok_response("auto-connect works")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            client = PlanReviewerGeminiClient(config)
            assert not client.is_connected
            result = await client.chat(_MESSAGES)
            assert result == "auto-connect works"
            await client.close()


# ---------------------------------------------------------------------------
# chat() error paths
# ---------------------------------------------------------------------------


class TestPlanReviewerGeminiClientChatErrors:
    """Test error handling in chat()."""

    @pytest.mark.asyncio
    async def test_auth_error_on_401(self) -> None:
        """401 raises PlanReviewerGeminiAuthError."""
        config = _make_config()
        mock_resp = _make_error_response(401, "Unauthorized")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiAuthError, match="401"):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_auth_error_on_403(self) -> None:
        """403 raises PlanReviewerGeminiAuthError."""
        config = _make_config()
        mock_resp = _make_error_response(403, "Forbidden")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiAuthError, match="403"):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_client_error_on_400(self) -> None:
        """Generic 4xx raises PlanReviewerGeminiClientError."""
        config = _make_config()
        mock_resp = _make_error_response(400, "Bad Request")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiClientError):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_client_error_on_500(self) -> None:
        """5xx raises PlanReviewerGeminiClientError."""
        config = _make_config()
        mock_resp = _make_error_response(500, "Internal Server Error")

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiClientError):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        """httpx.TimeoutException raises PlanReviewerGeminiTimeoutError."""
        config = _make_config()

        with _patch_client(AsyncMock(side_effect=httpx.TimeoutException("timed out"))):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiTimeoutError, match="timed out"):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_malformed_response_raises_client_error(self) -> None:
        """Missing 'choices' key raises PlanReviewerGeminiClientError."""
        config = _make_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"unexpected": "format"}
        mock_resp.text = '{"unexpected": "format"}'

        with _patch_client(AsyncMock(return_value=mock_resp)):
            async with PlanReviewerGeminiClient(config) as client:
                with pytest.raises(PlanReviewerGeminiClientError):
                    await client.chat(_MESSAGES)

    @pytest.mark.asyncio
    async def test_not_connected_execute_raises(self) -> None:
        """_execute_chat() raises if client is None."""
        config = _make_config()
        client = PlanReviewerGeminiClient(config)
        # Manually call _execute_chat without connecting
        with pytest.raises(PlanReviewerGeminiClientError, match="not connected"):
            await client._execute_chat({}, {})


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestPlanReviewerGeminiExceptionHierarchy:
    """Verify exception class hierarchy."""

    def test_auth_error_is_client_error(self) -> None:
        """PlanReviewerGeminiAuthError inherits PlanReviewerGeminiClientError."""
        assert issubclass(PlanReviewerGeminiAuthError, PlanReviewerGeminiClientError)

    def test_timeout_error_is_client_error(self) -> None:
        """PlanReviewerGeminiTimeoutError inherits PlanReviewerGeminiClientError."""
        assert issubclass(PlanReviewerGeminiTimeoutError, PlanReviewerGeminiClientError)

    def test_base_error_is_exception(self) -> None:
        """PlanReviewerGeminiClientError inherits Exception."""
        assert issubclass(PlanReviewerGeminiClientError, Exception)


# ---------------------------------------------------------------------------
# Import / __all__ tests
# ---------------------------------------------------------------------------


class TestPlanReviewerGeminiClientImports:
    """Verify public API exports."""

    def test_importable_from_clients_package(self) -> None:
        """All public symbols are importable from omniintelligence.clients."""
        from omniintelligence.clients import (
            ModelPlanReviewerGeminiConfig,
            PlanReviewerGeminiAuthError,
            PlanReviewerGeminiClient,
            PlanReviewerGeminiClientError,
            PlanReviewerGeminiTimeoutError,
        )

        assert ModelPlanReviewerGeminiConfig is not None
        assert PlanReviewerGeminiClient is not None
        assert PlanReviewerGeminiClientError is not None
        assert PlanReviewerGeminiAuthError is not None
        assert PlanReviewerGeminiTimeoutError is not None
