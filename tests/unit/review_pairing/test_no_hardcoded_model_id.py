# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Ratchet: no local review endpoint may declare a concrete model id.

OMN-18623. Operator ruling, in-session 2026-09-17T19:54:09Z, firm: the hostile
reviewer's model must not be hardcoded to a specific model id; a served-model
change must be solvable by an overlay or runtime resolution, never by a pull
request that repoints a literal.

THE HISTORY THIS EXISTS TO END
-------------------------------
    OMN-16407  2026-08-23  api_model_id -> "qwen3.8"
    OMN-17786  2026-09-03  api_model_id -> "Qwen3.6-35B-A3B"
    OMN-18623  2026-09-17  api_model_id -> "Qwen3.8-27B"   <- repin, then this

Three pull requests in four weeks, each repointing a copy of a fact owned by a
systemd unit on another host. Each stale copy was a deterministic HTTP 404 on
every local review leg and blocked every pull request in every consuming repo
until a human noticed.

WHY THE TWO EARLIER GUARDS COULD NOT HAVE STOPPED IT
-----------------------------------------------------
OMN-17786 shipped ``test_local_201_8000_keys_share_one_served_model_id``, which
asserts the keys on one endpoint carry ONE SHARED id. All three agreed
perfectly throughout the 2026-09-17 outage -- on a model that no longer
existed. Agreement is not correctness when the value being agreed on is written
in the same commit as the pins that carry it.

The first fix attempt on THIS ticket added a committed inventory file and
compared the pins against it. That was strictly better and still wrong in the
same direction: an inventory is one more declaration of somebody else's fact,
and keeping it current is the same manual step that had already failed twice.

This ratchet takes the value away instead. The assertion is not "the declared
id is correct" but "there is no declared id". Drift becomes unrepresentable
rather than detectable, which is the only form of this guard that does not
depend on a human noticing something.

SHAPE
-----
Modelled on the parser-option-strings tests in ``omninode_infra``
(``test_no_entrypoint_declares_a_health_status_option``): read the surface's
own text and fail if the forbidden affordance exists at all, so reintroducing
it is a red test rather than something a reviewer has to catch.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from omniintelligence.review_pairing.model_registry_loader import load_registry
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig

_REGISTRY_PATH: Path = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "omniintelligence"
    / "review_pairing"
    / "model_registry.yaml"
)

# Every id this field has carried. A ratchet that only knew the CURRENT value
# would pass the moment someone pasted the next one in.
_RETIRED_MODEL_IDS: tuple[str, ...] = (
    "qwen3.8",
    "Qwen3.6-35B-A3B",
    "Qwen3.8-27B",
)


def _local_http_endpoint_keys() -> dict[str, ModelEndpointConfig]:
    """Registry entries that resolve to a self-hosted HTTP endpoint.

    Scoped deliberately. A multi-model CLOUD endpoint has no single served
    model, so ``/v1/models`` is not a truth there and a declared id is a real
    choice this repository owns -- see ``glm-review``. Entries with an empty
    ``default_url`` are unrouted slots that cannot be called at all.
    """
    contract = load_registry()
    return {
        key: cfg
        for key, cfg in contract.models.items()
        if key in contract.local_model_keys and cfg.default_url.startswith("http")
    }


def test_the_scope_is_not_empty() -> None:
    """Positive control: the set this ratchet guards is non-empty.

    Without this, renaming a key or emptying a URL would make every assertion
    below vacuously true and the ratchet would report green while guarding
    nothing.
    """
    keys = _local_http_endpoint_keys()
    assert keys, (
        "no local model key resolves to an HTTP endpoint -- the join this "
        "ratchet depends on has changed shape and it has gone vacuous."
    )
    assert set(keys) == {"deepseek-r1", "qwen3-review", "qwen3-review-b"}, (
        f"unexpected local HTTP endpoint key set: {sorted(keys)}. If this is a "
        "deliberate roster change, update this control; do not delete it."
    )


def test_no_local_endpoint_declares_a_concrete_model_id() -> None:
    """THE RATCHET: a local endpoint entry must carry no model id literal."""
    offenders = sorted(
        f"  {key}: api_model_id={cfg.api_model_id!r} "
        f"(model_id_source={cfg.model_id_source!r})"
        for key, cfg in _local_http_endpoint_keys().items()
        if cfg.api_model_id or cfg.model_id_source != "served"
    )
    assert not offenders, (
        "a local review endpoint declares a concrete model id. The operator "
        "ruling of 2026-09-17T19:54:09Z forbids this: the served model is a "
        "fact owned by the host, and a copy of it here goes stale the moment "
        "the host changes, taking the Hostile Review Gate down in every "
        "consuming repo.\n" + "\n".join(offenders) + "\n\nUse "
        "model_id_source: served and let served_model_resolver read "
        "/v1/models on the routed endpoint."
    )


def test_no_retired_model_id_appears_as_a_declared_value() -> None:
    """No retired id may reappear as a VALUE anywhere in the registry.

    Text-level, deliberately: it catches a paste into a new field or a new
    entry that the typed assertions above would not reach yet. Comments are
    excluded because the file's provenance notes legitimately name every
    retired id, and stripping that history to satisfy a grep would trade real
    documentation for a passing test.
    """
    raw = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    found: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str) and node in _RETIRED_MODEL_IDS:
            found.append(f"  {path} = {node!r}")

    walk(raw, "registry")
    assert not found, (
        "a retired reviewer model id is declared as a value in "
        "model_registry.yaml:\n" + "\n".join(sorted(found)) + "\n\nThese ids "
        "belong to whatever the host happens to serve; the registry must not "
        "name one (OMN-16407 / OMN-17786 / OMN-18623)."
    )


def test_served_source_refuses_a_declared_id_at_load_time() -> None:
    """A config may not both resolve and declare its id.

    Without this the two could coexist, the literal would be dead text that
    still reads as authoritative, and the next lane would repin it -- the exact
    habit this ticket removes.
    """
    with pytest.raises(ValidationError) as excinfo:
        ModelEndpointConfig(
            env_var="LLM_X_URL",
            default_url="http://example.invalid:8000",
            kind="code_review",
            timeout_seconds=60.0,
            api_model_id="some-model",
            model_id_source="served",
        )
    assert "api_model_id must be empty" in str(excinfo.value)


def test_unknown_model_id_source_is_refused() -> None:
    """A typo must fail loudly, not silently fall back to 'declared'.

    Defaulting an unrecognised source would send an empty model id and produce
    a confusing endpoint error far from the cause.
    """
    with pytest.raises(ValidationError) as excinfo:
        ModelEndpointConfig(
            env_var="LLM_X_URL",
            default_url="http://example.invalid:8000",
            kind="code_review",
            timeout_seconds=60.0,
            model_id_source="servedd",
        )
    assert "model_id_source must be one of" in str(excinfo.value)


def test_declared_entries_are_untouched() -> None:
    """The cloud reviewer and the CLI fallback keep their declared ids.

    This ratchet must not become "no model id anywhere". A multi-model cloud
    endpoint's id is a choice this repo owns, and removing it would be a
    different defect, not a stricter version of this one.
    """
    contract = load_registry()
    glm = contract.models["glm-review"]
    assert glm.model_id_source == "declared"
    assert glm.api_model_id == "glm-5.3-flash"

    codex = contract.models["codex"]
    assert codex.model_id_source == "declared"
    assert codex.api_model_id == "codex"
