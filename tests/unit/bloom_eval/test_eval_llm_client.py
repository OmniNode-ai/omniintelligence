from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from omniintelligence.clients.eval_llm_client import (
    EvalLLMClient,
    EvalLLMConnectionError,
    EvalLLMTimeoutError,
)

GENERATOR_URL = "http://192.168.86.201:8001"
JUDGE_URL = "http://192.168.86.200:8101"


def _make_client() -> EvalLLMClient:
    return EvalLLMClient(generator_url=GENERATOR_URL, judge_url=JUDGE_URL)


def _make_chat_response(content: str = "scenario text", n: int = 1) -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"content": f"{content} {i}"}, "index": i} for i in range(n)
        ]
    }


@pytest.mark.unit
async def test_generate_scenarios_posts_to_generator_url() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = _make_chat_response("scenario", n=3)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        await client.connect()
        results = await client.generate_scenarios("test prompt", n=3)

    called_url = mock_post.call_args[0][0]
    assert called_url == f"{GENERATOR_URL}/v1/chat/completions"
    assert len(results) == 3


@pytest.mark.unit
async def test_judge_output_posts_to_judge_url() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "metamorphic_stability_score": 0.9,
        "compliance_theater_risk": 0.1,
        "ambiguity_flags": [],
        "invented_requirements": [],
        "missing_acceptance_criteria": [],
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        await client.connect()
        result = await client.judge_output("prompt", "output", ["indicator"])

    called_url = mock_post.call_args[0][0]
    assert called_url == f"{JUDGE_URL}/v1/chat/completions"
    assert "metamorphic_stability_score" in result


@pytest.mark.unit
async def test_generator_and_judge_use_different_urls() -> None:
    client = _make_client()
    gen_response = MagicMock()
    gen_response.json.return_value = _make_chat_response("s", n=1)
    gen_response.raise_for_status = MagicMock()

    judge_response = MagicMock()
    judge_response.json.return_value = {"score": 0.5}
    judge_response.raise_for_status = MagicMock()

    urls_called: list[str] = []

    async def fake_post(url: str, **_kwargs: Any) -> MagicMock:
        urls_called.append(url)
        if "8001" in url:
            return gen_response
        return judge_response

    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        await client.connect()
        await client.generate_scenarios("prompt", n=1)
        await client.judge_output("prompt", "output", [])

    assert any("8001" in u for u in urls_called), "generator URL not called"
    assert any("8101" in u for u in urls_called), "judge URL not called"


@pytest.mark.unit
async def test_context_manager_lifecycle() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = _make_chat_response("s", n=1)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        async with EvalLLMClient(GENERATOR_URL, JUDGE_URL) as client:
            assert client._connected is True
            await client.generate_scenarios("test", n=1)
    assert client._connected is False


@pytest.mark.unit
async def test_timeout_raises_eval_llm_timeout_error() -> None:
    client = _make_client()
    await client.connect()

    with patch(
        "httpx.AsyncClient.post",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        with pytest.raises(EvalLLMTimeoutError):
            await client.generate_scenarios("test", n=1)


@pytest.mark.unit
async def test_connection_error_raises_eval_llm_connection_error() -> None:
    client = _make_client()
    await client.connect()

    with patch(
        "httpx.AsyncClient.post",
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises(EvalLLMConnectionError):
            await client.generate_scenarios("test", n=1)


@pytest.mark.unit
async def test_no_os_getenv_in_module() -> None:
    """Verify ARCH-002: no os.getenv in eval_llm_client module."""
    import inspect

    import omniintelligence.clients.eval_llm_client as mod

    source = inspect.getsource(mod)
    assert "os.getenv" not in source
    assert "os.environ" not in source
