# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The log sanitizer's webhook redaction rows come from a contract (OMN-21623).

``utils/log_sanitizer_webhooks.yaml`` declares them; ``ModelWebhookPatterns`` is the
one reader. The sanitizer holds no webhook URL pattern in code, and a file that omits
a field of a row, or names an unknown one, fails to load rather than falling back.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from omniintelligence.models.log_sanitizer import (
    ModelWebhookPattern,
    ModelWebhookPatterns,
    ModelWebhookPatternsLoadError,
    webhook_patterns,
)
from omniintelligence.utils.log_sanitizer import LogSanitizer

pytestmark = pytest.mark.unit

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "omniintelligence"
_SHIPPED = _SOURCE_ROOT / "utils" / "log_sanitizer_webhooks.yaml"


def _shipped_document() -> dict[str, list[dict[str, str]]]:
    return yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))


def _write(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "log_sanitizer_webhooks.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_shipped_file_declares_the_slack_and_discord_rows_in_order() -> None:
    assert [row.replacement for row in webhook_patterns().rows] == [
        "[SLACK_WEBHOOK_URL]",
        "[DISCORD_WEBHOOK_URL]",
    ]


def test_the_default_patterns_carry_the_contract_rows_contiguously() -> None:
    rows = webhook_patterns().as_tuples()
    defaults = LogSanitizer.DEFAULT_PATTERNS
    start = defaults.index(rows[0])
    assert defaults[start : start + len(rows)] == rows


def test_the_sanitizer_source_holds_no_webhook_url_pattern() -> None:
    source = (_SOURCE_ROOT / "utils" / "log_sanitizer.py").read_text(encoding="utf-8")
    for row in webhook_patterns().rows:
        assert row.pattern not in source


@pytest.mark.parametrize("missing", sorted(ModelWebhookPattern.model_fields))
def test_a_row_missing_one_field_fails_to_load(tmp_path: Path, missing: str) -> None:
    document = _shipped_document()
    del document["rows"][0][missing]
    with pytest.raises(ModelWebhookPatternsLoadError, match=missing):
        ModelWebhookPatterns.load(_write(tmp_path, document))


def test_a_row_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    document = _shipped_document()
    document["rows"][0]["surprise"] = "x"
    with pytest.raises(ModelWebhookPatternsLoadError, match="surprise"):
        ModelWebhookPatterns.load(_write(tmp_path, document))


def test_a_file_without_rows_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelWebhookPatternsLoadError, match="rows"):
        ModelWebhookPatterns.load(_write(tmp_path, {"rows": []}))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelWebhookPatternsLoadError, match="not found"):
        ModelWebhookPatterns.load(tmp_path / "absent.yaml")
