# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The verifier's overlay: packaged defaults, a deployment overlay over them, and registration (OMN-22175)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

from omniintelligence.handlers.handler_review_agent_receipt_overlay import (
    NodeOverlayError,
    load_topics,
    load_verifier_settings,
)
from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    EnumAgentReceiptVerifyTransport,
)

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]


def test_packaged_overlay_fails_closed_without_a_deployment_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ONEX_SKILL_OVERLAY_ROOTS", raising=False)
    settings = load_verifier_settings()
    assert settings.transport is EnumAgentReceiptVerifyTransport.IN_MEMORY
    assert settings.quorum_size >= 2
    assert settings.policy.approved_identities == (), "the roster is deployment data"


def test_deployment_overlay_replaces_each_key_it_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "review_agent_receipt_verify" / "overlay.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"quorum_size": 3}), encoding="utf-8")
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(tmp_path))
    assert load_verifier_settings().quorum_size == 3


def test_a_broken_overlay_is_refused_not_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "review_agent_receipt_verify" / "overlay.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("quorum_size: 1\n", encoding="utf-8")
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(tmp_path))
    with pytest.raises(NodeOverlayError):
        load_verifier_settings()
    path.write_text("unknown_key: 1\n", encoding="utf-8")
    with pytest.raises(NodeOverlayError):
        load_verifier_settings()


def test_topics_follow_the_contract_naming() -> None:
    topics = load_topics()
    assert topics.command.startswith("onex.cmd.omniintelligence.")
    assert topics.decided.startswith("onex.evt.omniintelligence.")
    assert topics.command != topics.decided


def test_node_is_registered_in_the_entry_points() -> None:
    declared = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entry = declared["project"]["entry-points"]["onex.nodes"]
    assert (
        entry["node_review_agent_receipt_verify_compute"]
        == "omniintelligence.nodes.node_review_agent_receipt_verify_compute"
    )
