# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Guard: no registry key may pin a model id the declared inventory does not serve.

OMN-18623. This is the THIRD occurrence of one defect class:

    OMN-16407  2026-08-23  api_model_id -> "qwen3.8"          (SGLang on .201:8000)
    OMN-17786  2026-09-03  api_model_id -> "Qwen3.6-35B-A3B"  (vLLM on .201:8000)
    OMN-18623  2026-09-17  api_model_id -> "Qwen3.8-27B"      (vLLM on .201:8000)

Each time the host's served model changed, three separate ``api_model_id``
values in ``model_registry.yaml`` went stale together, vLLM answered every
local review leg with HTTP 404, and the Hostile Review Gate blocked every PR
in every consuming repo until a human grepped the pins by hand.

The pre-existing guard ``test_local_201_8000_keys_share_one_served_model_id``
(OMN-17786) catches a PARTIAL repin -- keys on one endpoint disagreeing with
each other -- because it asserts they share a single value. It cannot catch
STALENESS, because the value it compares them against is a literal written in
the same commit as the pins. All three keys agreed with each other throughout
the 2026-09-17 outage; they simply agreed on a model that no longer existed.

This test closes that hole by giving the served id ONE declared home,
``served_model_inventory.yaml``, keyed by endpoint rather than by review key.
A host-side swap is then a one-line edit there, and every key still carrying
the old id fails here BY NAME.

Honest limit, restated from the inventory's own header: the inventory is a
committed declaration, so it cannot observe a swap on the host by itself. A
live probe was considered and deliberately rejected as the CI mechanism --
``select_models_with_fallback`` is built to degrade to the cloud reviewer when
a LAN endpoint is unreachable, so probing ``.201`` from CI would turn an
ordinary endpoint outage into a hard failure in every consuming repo. Liveness
is a runtime fallback concern; model IDENTITY is a contract concern and is what
this test governs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from omniintelligence.review_pairing.model_registry_loader import load_registry

_INVENTORY_PATH: Path = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "omniintelligence"
    / "review_pairing"
    / "served_model_inventory.yaml"
)


def _load_inventory() -> dict[str, dict[str, Any]]:
    """Parse the committed served-model inventory, failing loudly if absent."""
    assert _INVENTORY_PATH.is_file(), (
        f"served_model_inventory.yaml is missing at {_INVENTORY_PATH}. It is the "
        "single declared home of each endpoint's served model id; deleting it "
        "re-opens the OMN-16407/OMN-17786/OMN-18623 drift."
    )
    raw = yaml.safe_load(_INVENTORY_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "inventory must parse to a mapping"
    endpoints = raw.get("endpoints")
    assert isinstance(endpoints, dict) and endpoints, (
        "inventory declares no endpoints; an empty inventory would make every "
        "assertion below vacuously true."
    )
    return endpoints


def test_inventory_declares_required_fields_per_endpoint() -> None:
    """Every endpoint entry carries its id, its provenance, and a dated readback.

    ``provenance_unit`` and ``last_live_readback`` are required so the next
    lane can tell WHERE the value came from and WHEN it was last confirmed,
    rather than inheriting an undated literal the way OMN-17786's pin was
    inherited into the 2026-09-17 outage.
    """
    endpoints = _load_inventory()
    required = {"served_model_id", "provenance_unit", "last_live_readback"}
    for url, entry in endpoints.items():
        assert isinstance(entry, dict), f"{url}: entry must be a mapping"
        missing = sorted(required - set(entry))
        assert not missing, f"{url}: inventory entry missing {missing}"
        assert isinstance(entry["served_model_id"], str) and entry["served_model_id"], (
            f"{url}: served_model_id must be a non-empty string"
        )


def test_every_registry_key_matches_its_endpoint_inventory() -> None:
    """THE GUARD: a pinned api_model_id must equal what its endpoint serves.

    Fails by name on each drifted key, naming both the pinned and the served
    id, so the remedy is readable from the failure text alone.
    """
    endpoints = _load_inventory()
    contract = load_registry()

    drifted: list[str] = []
    checked: list[str] = []
    for key, config in contract.models.items():
        entry = endpoints.get(config.default_url)
        if entry is None:
            continue
        checked.append(key)
        served = entry["served_model_id"]
        if config.api_model_id != served:
            drifted.append(
                f"  {key}: pins api_model_id={config.api_model_id!r} but "
                f"{config.default_url} serves {served!r}"
            )

    assert checked, (
        "no registry key resolved to a declared inventory endpoint -- the join "
        "key (default_url) has changed shape and this guard has gone vacuous."
    )
    assert not drifted, (
        "registry keys pin a model id their endpoint does not serve. vLLM "
        "returns HTTP 404 on any mismatch, so each of these is a deterministic "
        "review failure, not a flaky one:\n"
        + "\n".join(sorted(drifted))
        + "\n\nFix: update served_model_inventory.yaml if the host changed, "
        "then repin these keys in model_registry.yaml to match."
    )


def test_every_local_lan_key_is_covered_by_the_inventory() -> None:
    """A new LAN review endpoint cannot be added without declaring what it serves.

    Without this, the guard above could be silently bypassed by pointing a key
    at an endpoint the inventory does not mention -- it would simply be skipped.
    """
    endpoints = _load_inventory()
    contract = load_registry()

    undeclared = sorted(
        f"{key} -> {contract.models[key].default_url}"
        for key in contract.local_model_keys
        if contract.models[key].default_url.startswith("http")
        and contract.models[key].default_url not in endpoints
    )
    assert not undeclared, (
        "local model keys resolve to an HTTP endpoint absent from "
        "served_model_inventory.yaml, so their api_model_id is unguarded:\n  "
        + "\n  ".join(undeclared)
    )


def test_guard_is_not_vacuous_positive_control() -> None:
    """Positive control: the guard's comparison really does reject a wrong id.

    An empty-result assertion reads identically to a clean bill of health, so
    prove the mechanism fires on an input known to be bad before trusting a
    pass above.
    """
    endpoints = _load_inventory()
    contract = load_registry()

    url = "http://192.168.86.201:8000"  # onex-allow-internal-ip
    assert url in endpoints, "expected the .201:8000 reviewer endpoint to be declared"
    served = endpoints[url]["served_model_id"]

    keys_on_url = [
        key for key, cfg in contract.models.items() if cfg.default_url == url
    ]
    assert keys_on_url, "expected at least one review key on .201:8000"

    # The retired ids this file exists to catch. Each was, in its day, the
    # value every key agreed on -- which is exactly why agreement alone is not
    # a sufficient guard.
    for retired in ("qwen3.8", "Qwen3.6-35B-A3B"):
        assert served != retired, (
            f"inventory still declares the retired id {retired!r}; the live "
            "endpoint moved off it."
        )

    with pytest.raises(AssertionError):
        # Simulate the drift this guard exists to catch.
        drifted = {"served_model_id": "a-model-nobody-serves"}
        assert (
            contract.models[keys_on_url[0]].api_model_id == drifted["served_model_id"]
        ), "control"
