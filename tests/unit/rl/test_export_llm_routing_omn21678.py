# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The RL policy exporter derives its backend slugs and reads its model names from the overlay (OMN-21678).

``ACTION_TO_BACKEND`` is derived from the ``RoutingAction`` member names and
``BACKEND_MODELS`` is the ``OMNIINTELLIGENCE_RL_EXPORT_MODELS`` setting. Collected
only where torch is installed (see ``conftest.py``).
"""

from __future__ import annotations

import importlib

import pytest

from omniintelligence.models.llm_routing import llm_routing
from omniintelligence.rl import export
from omniintelligence.rl.contracts.actions import RoutingAction

pytestmark = pytest.mark.unit


def test_every_routing_action_has_a_distinct_backend_slug() -> None:
    assert set(export.ACTION_TO_BACKEND) == set(RoutingAction)
    assert len(set(export.ACTION_TO_BACKEND.values())) == len(RoutingAction)
    for action, slug in export.ACTION_TO_BACKEND.items():
        assert slug == action.name.lower().replace("_", "-")


def test_every_backend_has_a_url_entry() -> None:
    assert set(export.BACKEND_URLS) == set(export.ACTION_TO_BACKEND.values())


def test_backend_models_are_the_overlay_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = export.ACTION_TO_BACKEND[RoutingAction.EMBEDDING]
    monkeypatch.setenv("OMNIINTELLIGENCE_RL_EXPORT_MODELS", f'{{"{slug}": "served-x"}}')
    llm_routing.cache_clear()
    try:
        reloaded = importlib.reload(export)
        assert {slug: "served-x"} == reloaded.BACKEND_MODELS
    finally:
        monkeypatch.delenv("OMNIINTELLIGENCE_RL_EXPORT_MODELS")
        llm_routing.cache_clear()
        importlib.reload(export)
