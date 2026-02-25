# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""HTTP and DB client helpers for Gmail intent evaluation.

Lives in omniintelligence.clients (not inside nodes/) to comply with ARCH-002:
nodes must not import transport libraries (httpx, asyncpg, etc.) directly.

Provides:
  - fetch_url_content()         — URL fetch with 512KB cap, HTML strip
  - fetch_embedding()           — Qwen3-Embedding HTTP call
  - call_deepseek_r1()          — DeepSeek R1 chat completions call
  - make_asyncpg_repository()   — asyncpg connection factory returning ProtocolPatternRepository

Reference:
    - OMN-2790: HandlerGmailIntentEvaluate implementation
    - OMN-2787: Gmail Intent Evaluator epic
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

import httpx

if TYPE_CHECKING:
    from omniintelligence.protocols import ProtocolPatternRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

# Reserved IP ranges that must not be fetched (SSRF guard)
_BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.IPv4Network("127.0.0.0/8"),  # loopback
    ipaddress.IPv4Network("10.0.0.0/8"),  # RFC1918
    ipaddress.IPv4Network("172.16.0.0/12"),  # RFC1918
    ipaddress.IPv4Network("192.168.0.0/16"),  # RFC1918
    ipaddress.IPv4Network("169.254.0.0/16"),  # link-local
    ipaddress.IPv4Network("100.64.0.0/10"),  # shared address space
    ipaddress.IPv4Network("0.0.0.0/8"),  # "this" network
    ipaddress.IPv4Network("224.0.0.0/4"),  # multicast
    ipaddress.IPv4Network("240.0.0.0/4"),  # reserved
    ipaddress.IPv6Network("::1/128"),  # IPv6 loopback
    ipaddress.IPv6Network("fc00::/7"),  # IPv6 unique local
    ipaddress.IPv6Network("fe80::/10"),  # IPv6 link-local
    ipaddress.IPv6Network("ff00::/8"),  # IPv6 multicast
)


def _is_safe_fetch_target(url: str) -> bool:
    """Return True if url is safe to fetch (not SSRF-able).

    Checks:
    - Scheme must be http or https
    - Hostname must resolve to a non-reserved IP address
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        # Resolve all IPs for this hostname
        try:
            results = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False  # Cannot resolve → block

        for result in results:
            addr_str = result[4][0]
            try:
                addr = ipaddress.ip_address(addr_str)
            except ValueError:
                return False
            for network in _BLOCKED_NETWORKS:
                if addr in network:
                    logger.warning(
                        "SSRF guard blocked %s: resolved to reserved IP %s",
                        hostname,
                        addr_str,
                    )
                    return False
        return True
    except Exception as exc:
        logger.warning("SSRF check failed for %s: %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# URL content fetch
# ---------------------------------------------------------------------------

_URL_FETCH_MAX_BYTES: int = 524288  # 512KB
_URL_FETCH_TIMEOUT_SECONDS: float = 10.0
_URL_CONTENT_BUDGET_CHARS: int = 6000
_URL_PARAGRAPH_MIN_LEN: int = 40
_URL_PARAGRAPH_BUDGET: int = 20


async def fetch_url_content(url: str) -> tuple[str, str]:
    """Fetch URL content with 512KB cap and HTML stripping.

    Returns (content, status) where status is "OK" or "FAILED".
    Performs SSRF validation before fetching.
    """
    try:
        # SSRF guard: reject private/internal addresses
        if not _is_safe_fetch_target(url):
            logger.warning("URL fetch blocked by SSRF guard: %s", url)
            return "", "FAILED"

        headers = {"User-Agent": "Mozilla/5.0 (compatible; OmniNode/1.0)"}
        raw_buf = bytearray()
        content_type = ""

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_URL_FETCH_TIMEOUT_SECONDS
        ) as client:
            async with client.stream("GET", url, headers=headers) as r:
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                async for chunk in r.aiter_bytes():
                    raw_buf.extend(chunk)
                    if len(raw_buf) >= _URL_FETCH_MAX_BYTES:
                        break

        raw = bytes(raw_buf)[:_URL_FETCH_MAX_BYTES]

        if "text/html" in content_type:
            text = raw.decode("utf-8", errors="replace")
            # Strip script and style blocks
            text = re.sub(
                r"<(script|style)[^>]*>.*?</\1>",
                "",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            # Strip remaining tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()
        elif "application/json" in content_type:
            text = raw.decode("utf-8", errors="replace")[:8000]
        else:
            text = raw.decode("utf-8", errors="replace")

        # Extraction budget: title + first N paragraphs
        paragraphs = [
            p.strip()
            for p in text.split("\n")
            if len(p.strip()) > _URL_PARAGRAPH_MIN_LEN
        ]
        budget = " ".join(paragraphs[:_URL_PARAGRAPH_BUDGET])[
            :_URL_CONTENT_BUDGET_CHARS
        ]
        return budget, "OK"

    except Exception as exc:
        logger.warning("URL fetch failed for %s: %s", url, exc)
        return "", "FAILED"


# ---------------------------------------------------------------------------
# Embedding fetch
# ---------------------------------------------------------------------------


async def fetch_embedding(query_text: str, embedding_url: str) -> list[float]:
    """Fetch text embedding from Qwen3-Embedding endpoint.

    Returns embedding vector.

    Raises:
        httpx.HTTPError: On HTTP failure.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{embedding_url.rstrip('/')}/v1/embeddings",
            json={"input": query_text[:2000], "model": "Qwen3-Embedding-8B"},
        )
        resp.raise_for_status()
        return list(resp.json()["data"][0]["embedding"])


# ---------------------------------------------------------------------------
# DeepSeek R1 LLM call
# ---------------------------------------------------------------------------

_LLM_MAX_TOKENS: int = 1000
_LLM_TIMEOUT_SECONDS: float = 30.0


async def call_deepseek_r1(
    system_prompt: str,
    user_prompt: str,
    llm_url: str,
) -> str:
    """Call DeepSeek R1 chat completions endpoint.

    Returns raw response content string.

    Raises:
        httpx.HTTPError: On HTTP failure.
        KeyError: If response shape is unexpected.
    """
    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            f"{llm_url.rstrip('/')}/v1/chat/completions",
            json={
                "model": "deepseek-r1",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": _LLM_MAX_TOKENS,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        result: Any = resp.json()["choices"][0]["message"]["content"]
        return str(result)


# ---------------------------------------------------------------------------
# asyncpg repository factory
# ---------------------------------------------------------------------------


async def make_asyncpg_repository(
    db_url: str | None,
) -> ProtocolPatternRepository | None:
    """Create an asyncpg-backed repository from a DB URL.

    Returns None if db_url is not set (degraded mode: no idempotency).

    The asyncpg import lives here (in clients/) per ARCH-002 — transport
    libraries must not be imported inside nodes/.
    """
    if not db_url:
        return None
    try:
        import asyncpg

        from omniintelligence.protocols import ProtocolPatternRepository as _Repo

        conn = await asyncpg.connect(db_url)
        return cast(
            _Repo, conn
        )  # asyncpg.Connection satisfies ProtocolPatternRepository
    except Exception as exc:
        logger.warning(
            "Failed to connect to DB for idempotency (degraded mode): %s", exc
        )
        return None
