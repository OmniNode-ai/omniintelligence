# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Which reviewer a registry key actually is: its endpoint plus its model.

The cross-model quorum (OMN-18479) exists so that one model's opinion cannot
block a merge. It counted registry KEYS, and a key is only a name:
``qwen3-review``, ``qwen3-review-b`` and ``deepseek-r1`` were three names for
one endpoint serving one model, so two of them met the two-model quorum with
one model agreeing with itself (OMN-17492).

A reviewer's identity is the endpoint it resolves to plus the model it is
asked for there:

* ``model_id_source: served`` -- the endpoint serves exactly one model and the
  id is read from it at call time (OMN-18623), so the endpoint alone names the
  model. The model part is the literal ``served``.
* ``model_id_source: declared`` -- the endpoint may serve many models and the
  registry chooses one, so the declared ``api_model_id`` is part of the
  identity.

The endpoint is the URL the adapter will call, with the key's env-var
override applied, normalised so that spelling differences (a trailing
``/v1``, an implicit default port, letter case in the host) do not make one
endpoint look like two. A key with no URL (a CLI reviewer such as ``codex``,
or an entry whose URL is unset) is its own reviewer, ``key:<name>``.

Reference: OMN-17492.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping

from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
)

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}
_API_PATH_SUFFIXES: tuple[str, ...] = (
    "/v1/chat/completions",
    "/chat/completions",
    "/v1",
)


def _normalise_endpoint(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port or _DEFAULT_PORTS.get(scheme)
    path = parsed.path.rstrip("/")
    for suffix in _API_PATH_SUFFIXES:
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    netloc = f"{host}:{port}" if port is not None else host
    return f"{scheme}://{netloc}{path.rstrip('/')}"


def reviewer_identity(
    model_key: str,
    config: ModelEndpointConfig | None,
    environ: Mapping[str, str],
) -> str:
    """Return the distinct-reviewer identity of ``model_key``.

    Args:
        model_key: Registry key the caller asked for.
        config: That key's registry entry, or None when it has none.
        environ: Environment to read the key's URL override from.

    Returns:
        ``<normalised endpoint>#<model>`` where ``<model>`` is the declared
        ``api_model_id`` or ``served``; ``key:<model_key>`` when the key has
        no entry or no URL.
    """
    if config is None:
        return f"key:{model_key}"
    url = environ.get(config.env_var) or config.default_url
    if not url.strip():
        return f"key:{model_key}"
    if config.model_id_source == "served" or not config.api_model_id:
        model = "served"
    else:
        model = config.api_model_id
    return f"{_normalise_endpoint(url)}#{model}"


__all__ = ["reviewer_identity"]
