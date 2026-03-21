# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Configuration model for code crawler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelRepoCrawlConfig(BaseModel):
    """Configuration for a single repository to crawl."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1)
    enabled: bool = True
    path: str = Field(..., min_length=1)
    include: list[str] = Field(default_factory=lambda: ["src/**/*.py"])
    exclude: list[str] = Field(default_factory=lambda: ["**/__pycache__/**"])


class ModelCrawlConfig(BaseModel):
    """Configuration for the code crawler, read from contract YAML."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repos: list[ModelRepoCrawlConfig] = Field(default_factory=list)


__all__ = ["ModelCrawlConfig", "ModelRepoCrawlConfig"]
