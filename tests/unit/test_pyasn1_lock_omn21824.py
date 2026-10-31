# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The lockfile must select pyasn1 0.6.5 and the installed codec must round-trip."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def test_lock_selects_pyasn1_0_6_5() -> None:
    """One pyasn1 entry, with sdist and wheel URLs for 0.6.5."""
    packages = tomllib.loads((_ROOT / "uv.lock").read_text())["package"]
    matches = [p for p in packages if p["name"] == "pyasn1"]
    assert len(matches) == 1, matches
    package = matches[0]
    assert package["version"] == "0.6.5"
    assert package["sdist"]["url"].endswith("/pyasn1-0.6.5.tar.gz")
    assert package["wheels"]
    assert all(
        w["url"].endswith("/pyasn1-0.6.5-py3-none-any.whl") for w in package["wheels"]
    )


def test_installed_pyasn1_round_trips_ber_and_der() -> None:
    """The installed 0.6.5 decodes BER and DER integers without trailing data."""
    from pyasn1.codec.ber import decoder as ber_decoder
    from pyasn1.codec.ber import encoder as ber_encoder
    from pyasn1.codec.der import decoder as der_decoder
    from pyasn1.codec.der import encoder as der_encoder
    from pyasn1.type.univ import Integer

    assert version("pyasn1") == "0.6.5"
    for encoder, decoder in ((ber_encoder, ber_decoder), (der_encoder, der_decoder)):
        for value in (-129, 0, 127, 128, 65536):
            decoded, rest = decoder.decode(
                encoder.encode(Integer(value)), asn1Spec=Integer()
            )
            assert int(decoded) == value
            assert rest == b""


def test_lock_pyasn1_artifacts_are_consistent_with_0_6_5() -> None:
    """Every pyasn1 artifact in the lock carries a hash and names version 0.6.5."""
    packages = tomllib.loads((_ROOT / "uv.lock").read_text())["package"]
    (package,) = [p for p in packages if p["name"] == "pyasn1"]
    assert package["version"] == "0.6.5"
    assert package["sdist"]["hash"].startswith("sha256:")
    assert all(w["hash"].startswith("sha256:") for w in package["wheels"])
    assert "0.6.5" in package["sdist"]["url"]
    assert all("0.6.5" in w["url"] for w in package["wheels"])
