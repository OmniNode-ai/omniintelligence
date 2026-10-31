# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Webhook URL redaction rows of the log sanitizer (OMN-21623).

The rows live in ``utils/log_sanitizer_webhooks.yaml``; this model validates that
contract and is the one way code reads it. Every field of a row is required and
unknown fields are refused, so a file that omits or misspells one fails to load
instead of falling back to a value in code.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_CONTRACT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "utils" / "log_sanitizer_webhooks.yaml"
)


class ModelWebhookPatternsLoadError(RuntimeError):
    """Raised when ``log_sanitizer_webhooks.yaml`` is missing, malformed or incomplete."""


class ModelWebhookPattern(BaseModel):
    """One webhook URL redaction row.

    Attributes:
        pattern: Regular expression matching the webhook URL.
        replacement: Text the match is replaced with.
        description: What the row redacts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    pattern: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ModelWebhookPatterns(BaseModel):
    """The ordered webhook URL redaction rows.

    Attributes:
        rows: The rows, in the order the sanitizer applies them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rows: tuple[ModelWebhookPattern, ...] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelWebhookPatterns:
        """Read and validate the webhook redaction contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelWebhookPatternsLoadError: If the file is missing, not a mapping,
                or fails validation.
        """
        source = path or _CONTRACT_PATH
        if not source.is_file():
            raise ModelWebhookPatternsLoadError(
                f"log_sanitizer_webhooks.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelWebhookPatternsLoadError(
                f"log_sanitizer_webhooks.yaml failed to load: {exc}"
            ) from exc

    def as_tuples(self) -> list[tuple[str, str, str]]:
        """The rows as ``(pattern, replacement, description)`` tuples."""
        return [(row.pattern, row.replacement, row.description) for row in self.rows]


@cache
def webhook_patterns() -> ModelWebhookPatterns:
    """The shipped ``log_sanitizer_webhooks.yaml``, loaded once per process."""
    return ModelWebhookPatterns.load()


__all__ = [
    "ModelWebhookPattern",
    "ModelWebhookPatterns",
    "ModelWebhookPatternsLoadError",
    "webhook_patterns",
]
