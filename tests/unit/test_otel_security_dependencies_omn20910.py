# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The locked telemetry stack must admit the opentelemetry-api security update."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("package_name", ["opentelemetry-api", "opentelemetry-sdk"])
def test_locked_telemetry_excludes_affected_versions(package_name: str) -> None:
    """Both API and SDK must resolve beyond the affected 1.45.0 release."""
    lock = tomllib.loads((_ROOT / "uv.lock").read_text())
    versions = [
        Version(package["version"])
        for package in lock["package"]
        if package["name"] == package_name
    ]
    assert versions, f"{package_name} is absent from uv.lock"
    assert all(version >= Version("1.45.1") for version in versions), (
        f"{package_name} still resolves to an affected release: {versions}"
    )


@pytest.mark.parametrize(
    "package_name",
    [
        "opentelemetry-instrumentation",
        "opentelemetry-instrumentation-aiohttp-client",
        "opentelemetry-instrumentation-asyncpg",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-instrumentation-kafka-python",
        "opentelemetry-instrumentation-redis",
    ],
)
def test_contrib_constraints_admit_secure_telemetry(package_name: str) -> None:
    """Every infra instrumentation cap must allow the updated contrib family."""
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    overrides = {
        requirement.name: requirement.specifier
        for raw in project["tool"]["uv"]["override-dependencies"]
        for requirement in [Requirement(raw)]
    }
    assert package_name in overrides, f"{package_name} retains infra's contrib cap"
    assert overrides[package_name].contains("0.66b1", prereleases=True), (
        f"{package_name} excludes the contrib release for the secure API"
    )

    lock = tomllib.loads((_ROOT / "uv.lock").read_text())
    versions = [
        Version(package["version"])
        for package in lock["package"]
        if package["name"] == package_name
    ]
    assert versions, f"{package_name} is absent from uv.lock"
    for version in versions:
        assert version >= Version("0.66b1"), f"{package_name} retains an older API pin"
        assert overrides[package_name].contains(version, prereleases=True)
