# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Reject hardcoded Kafka fallbacks in selected Python files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_FALLBACK = re.compile(
    r"os\.getenv\(\s*['\"]KAFKA_[^'\"]+['\"]\s*,\s*['\"][^'\"]+['\"]"
)
_PRIVATE_BROKER = re.compile(
    r"192\.168\.\d+\.\d+:(?:9092|19092|29092|29093)"  # cloud-bus-ok OMN-19612
)


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "kafka-fallback-ok" in line or "noqa" in line:
            continue
        if _FALLBACK.search(line):
            findings.append(f"{path}:{lineno}: hardcoded Kafka env fallback")
        if _PRIVATE_BROKER.search(line) and "onex-allow-internal-ip" not in line:
            findings.append(f"{path}:{lineno}: hardcoded private-IP Kafka broker")
    return findings


def _paths(raw_paths: list[str]) -> list[Path]:
    selected = [Path(raw).resolve() for raw in raw_paths]
    full_scan = not selected or any(
        path == Path(__file__).resolve() or path.name == ".pre-commit-config.yaml"
        for path in selected
    )
    if not full_scan:
        return sorted(
            {path for path in selected if path.is_file() and path.suffix == ".py"}
        )
    return sorted((*Path("src").rglob("*.py"), *Path("scripts").rglob("*.py")))


def main(argv: list[str] | None = None) -> int:
    findings = [finding for path in _paths(argv or []) for finding in scan_file(path)]
    if findings:
        print("ERROR: hardcoded Kafka broker fallback detected:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
