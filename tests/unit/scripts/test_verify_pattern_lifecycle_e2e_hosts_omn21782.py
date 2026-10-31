# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The lifecycle verification script carries no host, address or port literal (OMN-21782)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from omnibase_core.validation.validator_contracts_and_di import (
    ValidatorContractsAndDi,
)

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "verify_pattern_lifecycle_e2e.py"
)
_RULES = {"literal_host", "literal_ip", "literal_port"}


@pytest.mark.unit
def test_script_has_no_host_ip_port_findings() -> None:
    assert _SCRIPT.is_file()
    result = ValidatorContractsAndDi().validate([_SCRIPT])
    assert result.metadata is not None
    assert result.metadata.files_processed == 1
    assert [i for i in result.issues if i.rule_name in _RULES] == []


@pytest.mark.unit
def test_missing_omnidash_dsn_skips_without_deriving_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMNIDASH_ANALYTICS_DB_URL", raising=False)
    monkeypatch.setenv("OMNIBASE_INFRA_DB_URL", "postgresql://u@db.example/infra")

    async def _connect(*_a: object, **_k: object) -> None:
        raise AssertionError("must not connect without OMNIDASH_ANALYTICS_DB_URL")

    fake = SimpleNamespace(connect=_connect)
    monkeypatch.setitem(sys.modules, "asyncpg", fake)
    spec = importlib.util.spec_from_file_location("verify_e2e", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert asyncio.run(module.check_context_utilization_events()) is False
