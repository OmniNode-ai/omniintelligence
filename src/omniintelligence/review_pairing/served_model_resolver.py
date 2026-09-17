# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Resolve the concrete model id a single-model endpoint actually serves.

OMN-18623. Operator ruling, in-session 2026-09-17T19:54:09Z, firm: the hostile
reviewer's model must not be hardcoded to a specific model id; a served-model
change must be solvable by an overlay or runtime resolution, never by a pull
request that repoints a literal.

WHY A LITERAL CANNOT WORK HERE
-------------------------------
The same field was repointed three times in four weeks -- OMN-16407
("qwen3.8"), OMN-17786 ("Qwen3.6-35B-A3B"), OMN-18623 ("Qwen3.8-27B") -- because
the model a host serves is decided by a systemd unit on that host, not by this
repository. vLLM validates the ``model`` field and answers any mismatch with
HTTP 404, so a stale literal is a deterministic outage of every local review
leg, and the remedy was always a pull request landing hours after the break.

A declared id is a COPY of a fact owned elsewhere. This module reads the fact
instead. vLLM serves exactly one model per port, so ``GET /v1/models`` on the
routed endpoint IS the truth, and after this change a served-model swap needs no
edit in any repository.

WHY NOT AN OVERLAY FILE
-----------------------
The ruling permits an overlay. One was considered and not taken: an overlay is
still a file a human edits when the served model changes, which is the same
shape as the literal, only relocated. It would be the right mechanism for a
value this repository OWNS; the served model id is a value it merely observes.
The per-environment overlay remains available as the declared override path for
an endpoint that is genuinely multi-model (see ``model_id_source: declared``),
which is why ``glm-review`` keeps an explicit id.

FAIL-CLOSED, AND SCOPED TO ONE MODEL
------------------------------------
Every ambiguous outcome raises. An unreachable endpoint, a malformed payload, a
response listing zero models, or a response listing MORE than one all refuse
rather than guess -- a multi-model response means the "exactly one model per
port" premise does not hold for that endpoint and a caller must declare which
one it wants. The refusal names the endpoint and what was actually returned, so
the next lane reads the cause instead of a bare 404.

Reachability is NOT this module's concern. ``select_models_with_fallback``
already drops unreachable local endpoints and degrades to the cloud reviewer;
a resolution failure surfaces through the same per-model failure path as any
other error and never takes down the rest of the roster.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Final

_MODELS_PATH: Final[str] = "/v1/models"
_DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0

# Resolution is a property of the endpoint, not of the review, and a roster
# calls the same endpoint more than once per run (qwen3-review and
# qwen3-review-b are two legs on one port). Cache per process so a roster pays
# one extra HTTP round trip rather than one per leg. Never cached across
# processes: a CI job that outlives a model swap is not a scenario, because a
# job is minutes long and a swap takes the endpoint down.
_CACHE: dict[str, str] = {}
_CACHE_LOCK: Final[threading.Lock] = threading.Lock()


class ServedModelResolutionError(RuntimeError):
    """Raised when an endpoint's served model id cannot be resolved exactly."""


def _models_url(base_url: str) -> str:
    """Build the ``/v1/models`` URL for a registry base URL."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        # A registry entry may carry a COMPLETE chat-completions URL (the cloud
        # shape). In an OpenAI-compatible API ``models`` is the SIBLING of
        # ``chat/completions`` under the same version prefix, whatever that
        # prefix is spelled -- /v1 upstream, /api/coding/paas/v4 on z.ai -- so
        # swap the leaf rather than assuming the prefix.
        return f"{normalized[: -len('/chat/completions')]}/models"
    # Host:port form (the self-hosted shape): the API root is the origin.
    return f"{normalized}{_MODELS_PATH}"


def resolve_served_model_id(
    base_url: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    use_cache: bool = True,
) -> str:
    """Return the single model id ``base_url`` serves.

    Args:
        base_url: The endpoint the review will be POSTed to, as the registry
            resolves it. Host:port form or a complete chat-completions URL.
        timeout_seconds: Budget for the metadata request. Deliberately small
            and independent of the review timeout -- this call returns in
            milliseconds on a healthy endpoint, and waiting minutes on it
            would spend the review's budget learning nothing.
        use_cache: Whether to read and write the per-process cache.

    Returns:
        The exact model id to send in the chat-completion ``model`` field.

    Raises:
        ServedModelResolutionError: If the endpoint is unreachable, answers
            something that is not parseable model metadata, or does not serve
            exactly one model. Never returns a guess.
    """
    if not base_url:
        raise ServedModelResolutionError(
            "cannot resolve a served model id from an empty endpoint URL"
        )

    if use_cache:
        with _CACHE_LOCK:
            cached = _CACHE.get(base_url)
        if cached is not None:
            return cached

    url = _models_url(base_url)
    request = urllib.request.Request(url, method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            raw = response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ServedModelResolutionError(
            f"could not read the served model id from {url}: {exc}. The review "
            "cannot choose a model id without it, and guessing is what "
            "OMN-16407/OMN-17786/OMN-18623 each cost a day to undo."
        ) from exc

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ServedModelResolutionError(
            f"{url} did not return JSON model metadata: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ServedModelResolutionError(
            f"{url} returned {type(payload).__name__}, expected a JSON object"
        )

    entries = payload.get("data")
    if not isinstance(entries, list):
        raise ServedModelResolutionError(
            f"{url} returned no 'data' list; got keys {sorted(payload)}"
        )

    ids: list[str] = [
        str(entry["id"])
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]
    ]

    if len(ids) != 1:
        raise ServedModelResolutionError(
            f"{url} serves {len(ids)} models {sorted(ids)}, expected exactly "
            "one. Runtime resolution assumes one model per port (the vLLM "
            "shape). An endpoint serving several must declare which one it "
            "wants with model_id_source: declared plus an explicit "
            "api_model_id."
        )

    served = ids[0]
    if use_cache:
        with _CACHE_LOCK:
            _CACHE[base_url] = served
    return served


def clear_cache() -> None:
    """Drop the per-process resolution cache. Test seam; not used in review."""
    with _CACHE_LOCK:
        _CACHE.clear()
