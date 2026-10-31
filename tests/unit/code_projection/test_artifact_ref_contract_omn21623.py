# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The code projection's artifact reference prefix comes from a contract (OMN-21623).

``code_projection/artifact_ref.yaml`` declares it; ``ModelArtifactRefContract`` is the
one reader. The modules hold no copy of the prefix, and a file that omits the field,
or names an unknown one, fails to load rather than falling back to a value in code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter

from omniintelligence.models.code_projection import (
    ArtifactRef,
    ModelArtifactRefContract,
    ModelArtifactRefContractLoadError,
    artifact_digest,
    artifact_digest_or_none,
    artifact_ref_contract,
    artifact_ref_for,
    artifact_ref_pattern,
)

pytestmark = pytest.mark.unit

_DIGEST = "ab" * 32
_SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "omniintelligence"
_SHIPPED = _SOURCE_ROOT / "code_projection" / "artifact_ref.yaml"


def _write(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "artifact_ref.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_shipped_file_declares_exactly_the_prefix() -> None:
    document = yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))
    assert set(document) == set(ModelArtifactRefContract.model_fields)
    assert artifact_ref_contract().prefix == document["prefix"]


def test_a_reference_is_the_prefix_then_the_digest() -> None:
    assert artifact_ref_for(_DIGEST) == f"{artifact_ref_contract().prefix}{_DIGEST}"


def test_the_digest_of_a_reference_round_trips() -> None:
    assert artifact_digest_or_none(artifact_ref_for(_DIGEST)) == _DIGEST
    assert artifact_digest(artifact_ref_for(_DIGEST)) == _DIGEST


def test_a_string_without_the_prefix_names_no_digest() -> None:
    assert artifact_digest_or_none(_DIGEST) is None
    assert artifact_digest_or_none("sha256:" + _DIGEST) is None
    with pytest.raises(ValueError, match="not a SHA-256 artifact URI"):
        artifact_digest(_DIGEST)


def test_the_pattern_accepts_a_well_formed_reference_only() -> None:
    pattern = re.compile(artifact_ref_pattern())
    assert TypeAdapter(ArtifactRef).validate_python(artifact_ref_for(_DIGEST))
    assert pattern.fullmatch(artifact_ref_for(_DIGEST))
    assert not pattern.fullmatch(artifact_ref_for(_DIGEST[:-1]))
    assert not pattern.fullmatch(artifact_ref_for(_DIGEST.upper()))
    assert not pattern.fullmatch(_DIGEST)


def test_a_file_missing_the_prefix_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactRefContractLoadError, match="prefix"):
        ModelArtifactRefContract.load(_write(tmp_path, {}))


def test_a_file_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactRefContractLoadError, match="surprise"):
        ModelArtifactRefContract.load(
            _write(tmp_path, {"prefix": "x://y/", "surprise": 1})
        )


def test_an_empty_prefix_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactRefContractLoadError, match="prefix"):
        ModelArtifactRefContract.load(_write(tmp_path, {"prefix": ""}))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactRefContractLoadError, match="not found"):
        ModelArtifactRefContract.load(tmp_path / "absent.yaml")


def test_no_projection_module_holds_a_copy_of_the_prefix() -> None:
    prefix = artifact_ref_contract().prefix
    offenders = [
        str(path.relative_to(_SOURCE_ROOT))
        for path in (_SOURCE_ROOT / "code_projection").rglob("*.py")
        if "node_tests" not in path.parts and prefix in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
