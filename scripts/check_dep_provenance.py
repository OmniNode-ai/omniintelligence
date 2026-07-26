#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dep-provenance gate — forbid first-party git-source overrides on dev/main,
and fail closed on stale cross-repo git pins.

Root cause this closes (OMN-13873): omnibase_infra PR #2184 merged to dev
carrying ``[tool.uv.sources]`` git-rev overrides pinning ``omnibase-core`` /
``omnibase-spi`` to UNRELEASED commits. Every CI check passed because CI
resolved those exact commits and ran green against them — the breakage is
dependency *provenance*, not runtime behavior, so no test catches it. This is a
pure static provenance gate: it FAILS closed if any PyPI-published first-party
dependency is sourced from git instead of PyPI.

Forbidden first-party deps (both hyphen and underscore spellings):

    omnibase-core   omnibase-spi   omnibase-compat

A ``[tool.uv.sources]`` entry for any of the above with a ``git`` / ``rev`` /
``branch`` / ``tag`` key is a forbidden override and fails the gate.

``onex-change-control`` is deliberately NOT checked by the forbidden-override
check — it follows an immutable-main pin release model (different from the
three PyPI-released deps), so its git pin is intentional and must remain
allowed.

Escape hatch (Rule-10 style): a forbidden source line may carry an inline
comment ``# raw-override-ok: <ticket>`` with a NON-EMPTY token. This exempts the
single line. An empty token (``# raw-override-ok:`` with nothing after) does NOT
exempt — the gate still fails. Because the TOML parser drops comments, the token
is detected by reading the raw source line for each flagged package.

Second gate — staleness (OMN-15144): every root cause above only forbade git
sourcing for 3 packages, but the OMN-15129 incident showed a *permitted*
cross-repo git pin (``omnibase-infra``, not in the forbidden set) sitting 240
commits behind its own repo's ``dev`` HEAD, silently withholding a merged fix
and producing a false-degrade CI signal for weeks. This gate closes the CLASS,
not just that one instance: any ``[tool.uv.sources]`` entry with a git ``rev``
pin (fixed SHA) is checked for how many commits behind the source repo's
``dev`` HEAD it is. More than ``--max-commits-behind`` (default 50) fails
closed. ``branch``/``tag`` pins track a moving ref and are exempt from this
specific check (they cannot go stale the way a frozen SHA can).
``onex-change-control`` is exempt from the staleness check too, for the same
immutable-main-model reason as the forbidden-override check. The same
``# raw-override-ok: <ticket>`` annotation exempts a staleness violation on
that line (a deliberate, ticket-tracked hold).

Exit codes:
    0  — no forbidden first-party git-source override AND no stale cross-repo
         git pin
    1  — a forbidden override was found, a stale pin was found, a pinned SHA
         could not be resolved (fail-closed), or a hard error (missing file)

The forbidden-override check is deterministic and offline (no network calls).
The staleness check requires network access — it fetches commit history from
each pinned package's git remote to compute commits-behind. Any fetch/resolve
failure is a HARD FAIL (fail-closed), never a silent skip.

Usage::

    uv run python scripts/check_dep_provenance.py
    uv run python scripts/check_dep_provenance.py --pyproject pyproject.toml
    uv run python scripts/check_dep_provenance.py --max-commits-behind 50
    uv run python scripts/check_dep_provenance.py --skip-staleness-check  # offline/CI-degraded mode
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

# ---------------------------------------------------------------------------
# First-party PyPI-published deps that must be resolved from PyPI, never git.
# Names are stored in canonical hyphen form; underscore spellings are
# normalized on lookup so both `omnibase-core` and `omnibase_core` are caught.
# ---------------------------------------------------------------------------

_FORBIDDEN_PACKAGES: frozenset[str] = frozenset(
    {
        "omnibase-core",
        "omnibase-spi",
        "omnibase-compat",
    }
)

# Source-override keys that indicate a git provenance (any one is forbidden for
# a first-party dep). A PyPI source has none of these.
_GIT_SOURCE_KEYS: frozenset[str] = frozenset({"git", "rev", "branch", "tag"})

# Inline escape token: `# raw-override-ok: <ticket>` with a non-empty token.
_ESCAPE_TOKEN_RE = re.compile(r"#\s*raw-override-ok:\s*(\S+)")

# ---------------------------------------------------------------------------
# [tool.uv.sources] parsing — regex-based, adapted (with attribution) from
# scripts/check-pinned-wheels.py::_parse_uv_sources. Copied rather than imported
# because that module's filename contains a hyphen (not a clean import target).
# We parse only the uv.sources block, which is sufficient for provenance.
#
# Note: the header pattern is anchored with ``^`` (start-of-line) so a commented
# ``#   [tool.uv.sources]`` example elsewhere in the file (as this repo carries
# in its dependency-guidance comments) does not shadow the real section.
# ---------------------------------------------------------------------------

_UVS_BLOCK_RE = re.compile(
    r"^\[tool\.uv\.sources\](.*?)(?=^\[|\Z)",
    re.MULTILINE | re.DOTALL,
)
_UVS_ENTRY_RE = re.compile(
    r"^(\S+)\s*=\s*\{([^}]+)\}",
    re.MULTILINE,
)
_KV_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _normalize(pkg: str) -> str:
    """Canonicalize a package name to hyphen form for comparison."""
    return pkg.strip().strip('"').strip("'").replace("_", "-").lower()


def _uv_sources_block(text: str) -> str | None:
    """Return the raw text of the [tool.uv.sources] block, or None if absent."""
    block_m = _UVS_BLOCK_RE.search(text)
    return block_m.group(1) if block_m else None


def _parse_uv_source_entries(block: str) -> dict[str, dict[str, str]]:
    """Return {normalized_pkg: {key: value}} for [tool.uv.sources] entries."""
    sources: dict[str, dict[str, str]] = {}
    for entry_m in _UVS_ENTRY_RE.finditer(block):
        pkg = _normalize(entry_m.group(1))
        kv_str = entry_m.group(2)
        sources[pkg] = dict(_KV_RE.findall(kv_str))
    return sources


def _line_for_package(block: str, pkg: str) -> str | None:
    """Return the raw source line (with any trailing comment) declaring `pkg`."""
    for raw_line in block.splitlines():
        stripped = raw_line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        # Entry key is the text before the first '=' on the line.
        key = stripped.split("=", 1)[0]
        if _normalize(key) == pkg:
            return raw_line
    return None


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------


def find_violations(text: str) -> list[str]:
    """Return diagnostic messages for each forbidden git-source override.

    An empty list means the file is clean (exit 0). A non-empty list means the
    gate fails (exit 1). Lines carrying a valid `# raw-override-ok: <token>`
    escape are excluded.
    """
    block = _uv_sources_block(text)
    if block is None:
        # No [tool.uv.sources] block at all — nothing can be overridden.
        return []

    entries = _parse_uv_source_entries(block)
    violations: list[str] = []

    for pkg, attrs in entries.items():
        if pkg not in _FORBIDDEN_PACKAGES:
            continue
        git_keys = sorted(_GIT_SOURCE_KEYS & set(attrs))
        if not git_keys:
            # A non-git source (unusual, but not a provenance violation).
            continue

        raw_line = _line_for_package(block, pkg)
        if raw_line is not None:
            escape_m = _ESCAPE_TOKEN_RE.search(raw_line)
            if escape_m and escape_m.group(1).strip():
                # Valid non-empty escape token — this line is exempt.
                continue

        keys_desc = ", ".join(f"{k}={attrs[k]!r}" for k in git_keys)
        violations.append(
            f"{pkg}: forbidden git-source override ({keys_desc}). "
            f"First-party deps must resolve from PyPI, not git. "
            f"line: {raw_line.strip() if raw_line else '<unresolved>'}"
        )

    return violations


# ---------------------------------------------------------------------------
# Staleness check (OMN-15144)
# ---------------------------------------------------------------------------

#: Default staleness ceiling. Justification (see ticket OMN-15144): the two
#: live incidents this closes (OMN-15129's omnibase-infra pin, and the
#: omnimarket pin found while building this gate) were 240+ and 217 commits
#: behind respectively — two orders of magnitude past any reasonable
#: threshold. 50 commits is roughly 1-3 days of normal fleet velocity (see
#: OMN-15052: omnibase_core accumulated 225 commits in 16 days, ~14/day),
#: giving a wide safety margin against false-positives on a pin refreshed
#: within the last few days, while catching drift within about a week — well
#: before it reaches the 200+ commit range that produced false-degrade
#: signals.
DEFAULT_MAX_COMMITS_BEHIND = 50

#: Packages exempt from the staleness check for the same reason they are
#: exempt from the forbidden-override check: an intentional, non-dev-line pin
#: model (immutable-main releases), not a repo tracking `dev`.
_STALENESS_EXEMPT_PACKAGES: frozenset[str] = frozenset({"onex-change-control"})


class StalenessResolutionError(RuntimeError):
    """Raised when commits-behind cannot be determined. Callers must treat
    this as a hard failure (fail-closed), never a silent skip."""


def _run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise StalenessResolutionError(
            f"git command failed ({' '.join(args)}): {result.stderr.strip()}"
        )
    return result


def default_commits_behind_resolver(
    git_url: str, pinned_sha: str, base_ref: str
) -> int:
    """Resolve how many commits `pinned_sha` is behind `origin/<base_ref>` on
    `git_url`, via a blobless bare-clone fetch (network required; no blobs are
    downloaded, only commit-graph metadata).

    Raises `StalenessResolutionError` on any failure — an unreachable SHA
    (deleted branch, unpublished commit, disallowed by server config), a
    network failure, or an unparsable result. Callers MUST fail closed on
    this exception, never treat it as "not stale."
    """
    with tempfile.TemporaryDirectory() as tmp:
        _run_git(["git", "init", "--bare", "-q", "."], cwd=tmp)
        _run_git(
            [
                "git",
                "fetch",
                "--filter=blob:none",
                "-q",
                git_url,
                f"+refs/heads/{base_ref}:refs/remotes/origin/{base_ref}",
            ],
            cwd=tmp,
        )
        try:
            _run_git(
                [
                    "git",
                    "fetch",
                    "--filter=blob:none",
                    "-q",
                    git_url,
                    f"{pinned_sha}:refs/pinned",
                ],
                cwd=tmp,
            )
        except StalenessResolutionError as exc:
            raise StalenessResolutionError(
                f"pinned SHA {pinned_sha!r} not fetchable from {git_url} "
                f"(deleted branch, unpublished commit, or server disallows "
                f"arbitrary-SHA fetch): {exc}"
            ) from exc
        result = _run_git(
            [
                "git",
                "rev-list",
                "--count",
                f"refs/pinned..refs/remotes/origin/{base_ref}",
            ],
            cwd=tmp,
        )
        try:
            return int(result.stdout.strip())
        except ValueError as exc:
            raise StalenessResolutionError(
                f"could not parse commit count from git rev-list output: "
                f"{result.stdout!r}"
            ) from exc


CommitsBehindResolver = Callable[[str, str, str], int]


def find_staleness_violations(
    text: str,
    *,
    max_commits_behind: int = DEFAULT_MAX_COMMITS_BEHIND,
    resolver: CommitsBehindResolver = default_commits_behind_resolver,
) -> list[str]:
    """Return diagnostic messages for stale/unresolvable cross-repo git pins.

    Checks every `[tool.uv.sources]` entry that carries a git `rev` (a frozen
    SHA — `branch`/`tag` pins track a moving ref and are exempt from this
    specific check). `onex-change-control` is exempt (immutable-main model).
    A line with a valid non-empty `# raw-override-ok: <ticket>` escape is
    exempt. An unresolvable SHA is a violation, not a skip (fail-closed).
    """
    block = _uv_sources_block(text)
    if block is None:
        return []

    entries = _parse_uv_source_entries(block)
    violations: list[str] = []

    for pkg, attrs in entries.items():
        if pkg in _STALENESS_EXEMPT_PACKAGES:
            continue
        git_url = attrs.get("git")
        pinned_sha = attrs.get("rev")
        if not git_url or not pinned_sha:
            # No git source, or a branch/tag pin (moving ref) — not applicable.
            continue

        raw_line = _line_for_package(block, pkg)
        if raw_line is not None:
            escape_m = _ESCAPE_TOKEN_RE.search(raw_line)
            if escape_m and escape_m.group(1).strip():
                # Valid non-empty escape token — this line is exempt.
                continue

        try:
            commits_behind = resolver(git_url, pinned_sha, "dev")
        except StalenessResolutionError as exc:
            violations.append(
                f"{pkg}: cross-repo git pin at {pinned_sha!r} ({git_url}) "
                f"could not be resolved against 'dev' HEAD — failing closed. "
                f"{exc}"
            )
            continue

        if commits_behind > max_commits_behind:
            violations.append(
                f"{pkg}: cross-repo git pin at {pinned_sha!r} is "
                f"{commits_behind} commits behind {git_url} 'dev' HEAD "
                f"(max allowed: {max_commits_behind}). Refresh the pin, or "
                f"annotate the line with '# raw-override-ok: <ticket>' for a "
                f"deliberate, ticket-cited hold. "
                f"line: {raw_line.strip() if raw_line else '<unresolved>'}"
            )

    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    parser.add_argument(
        "--max-commits-behind",
        type=int,
        default=DEFAULT_MAX_COMMITS_BEHIND,
        help=f"Staleness ceiling for cross-repo git pins (default: {DEFAULT_MAX_COMMITS_BEHIND})",
    )
    parser.add_argument(
        "--skip-staleness-check",
        action="store_true",
        help=(
            "Skip the network-dependent staleness check (forbidden-override "
            "check still runs). Use only for offline/degraded environments — "
            "never as a routine CI flag."
        ),
    )
    args = parser.parse_args(argv)

    pyproject_path = Path(args.pyproject)
    if not pyproject_path.exists():
        print(
            f"ERROR: pyproject.toml not found: {pyproject_path}",
            file=sys.stderr,
        )
        return 1

    text = pyproject_path.read_text()
    violations = find_violations(text)
    staleness_violations: list[str] = []
    if not args.skip_staleness_check:
        # Reference the module-global resolver by name (not as a bound default
        # argument) so it can be monkeypatched by callers/tests at run time.
        staleness_violations = find_staleness_violations(
            text,
            max_commits_behind=args.max_commits_behind,
            resolver=default_commits_behind_resolver,
        )

    if violations:
        print(
            "FAIL: forbidden first-party git-source override(s) in "
            f"{pyproject_path} [tool.uv.sources]:",
            file=sys.stderr,
        )
        for msg in violations:
            print(f"  - {msg}", file=sys.stderr)
        print(
            "\nomnibase-core / omnibase-spi / omnibase-compat are PyPI-published "
            "first-party deps and must NOT be pinned to git commits/branches/tags "
            "on dev/main. Resolve them from PyPI (release the dep first if the "
            "needed version is unpublished). If a temporary override is genuinely "
            "unavoidable, annotate the exact line with "
            "'# raw-override-ok: <ticket>' (non-empty token).",
            file=sys.stderr,
        )

    if staleness_violations:
        print(
            "FAIL: stale or unresolvable cross-repo git pin(s) in "
            f"{pyproject_path} [tool.uv.sources]:",
            file=sys.stderr,
        )
        for msg in staleness_violations:
            print(f"  - {msg}", file=sys.stderr)
        print(
            "\nA cross-repo git pin more than --max-commits-behind commits "
            "stale silently withholds merged fixes on the pinned repo and can "
            "produce false CI signals (OMN-15129). Refresh the pin to a "
            "recent dev HEAD SHA, or annotate the line with "
            "'# raw-override-ok: <ticket>' for a deliberate, ticket-cited "
            "hold.",
            file=sys.stderr,
        )

    if violations or staleness_violations:
        return 1

    print(
        f"OK: no forbidden first-party git-source override and no stale "
        f"cross-repo git pin in {pyproject_path} [tool.uv.sources]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
