# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Fail-closed gate: a workflow may not execute a repo-local script that is absent.

OMN-16664 (root cause). The OMN-15017 fan-out copied `call-occ-autobind.yml`
and `call-occ-companion-effect.yml` into this repo. Both carry a
`workflow_dispatch` manual-replay job whose first real step is

    run: python3 scripts/ci/occ_manual_replay_precheck.py pr_state.json

but the fan-out never carried `scripts/ci/occ_manual_replay_precheck.py` with
them. Live shape (omnibase_compat run 33001337186, omnimemory run
33019346585):

    python3: can't open file '/home/runner/work/.../occ_manual_replay_precheck.py'
    [Errno 2] No such file or directory

That entrypoint is the ONLY sanctioned recovery when the OCC born path misses
a mint, so the documented remediation was a dead end in every fanned-in repo
for weeks. It failed CLOSED, so nothing bad was ever published — the cost was
a recovery path that silently did not exist, discovered only when someone
needed it during an incident.

The defect class is broader than one script: a `run:` step naming a path in
this repo is an unchecked claim about the tree. Nothing resolved those claims.
This module resolves them.

## What is asserted

Every `scripts/**` path with a `.py` or `.sh` suffix that a `run:` step in
`.github/workflows/` executes **from the repository root** must exist in the
tree. Statically, from parsed YAML — no network, no GitHub token, no runner.

## What is deliberately NOT asserted, and why

* **Steps with a `working-directory`.** The OCC workflows check
  `OmniNode-ai/omnimarket` out into `.occ-autobind-src` and then run
  `python scripts/publish_occ_autobind_command.py` with
  `working-directory: .occ-autobind-src`. That path is a claim about
  *omnimarket's* tree, resolved at runtime into a directory that does not and
  should not exist here. Demanding it locally would be a false positive that
  gets the gate disabled, which is worse than the gap.
* **Every step after a foreign checkout into the workspace root.**
  A job that opens with `actions/checkout` of another repo and no `path:`
  leaves the workspace root holding *that* repo's tree, so every later
  `scripts/...` path in the job is a claim about the foreign repo, not this
  one. No workflow in this tree currently has that shape (the former live
  instance, `cr-thread-gate.yml`, was deleted in OMN-16933); the exclusion is
  retained because the shape is reachable and silently mis-flagging it would
  get the gate disabled. Detected as
  `uses: actions/checkout` carrying an explicit `repository:` and no non-root
  `path:` — a self-checkout omits `repository:`, which is what separates the
  two.
* **Paths under another prefix** (`.occ-autobind-src/scripts/x.py`,
  `../foo/scripts/x.py`). Same reason: not a claim about this tree.

Both exclusions are returned by `collect_script_references` and printed by the
CLI, so the gate's blind spots are stated on every run rather than hidden.
* **Whether the script actually works.** Existence only. The precheck's own
  behaviour is covered where it is exercised.

## Vacuity

A static extractor that quietly stops matching passes every existence
assertion and reports green forever — the same shape as the bug it guards
against. Three defences: the extractor is unit-tested against synthetic
workflows with known answers (positive AND negative cases), and
`test_repo_workflows_reference_at_least_one_local_script` fails if the real
tree yields zero references. If this repo ever legitimately stops running any
repo-local script from a workflow, delete that test together with this
module — do not weaken it in place.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

#: A repo-root-relative script path as it appears inside a shell `run:` body.
#: The lookbehind rejects any token that already carries a directory prefix
#: (`.occ-autobind-src/scripts/x.py`, `../scripts/x.py`) or is a suffix of a
#: longer word — those are not claims about this repo's tree.
_SCRIPT_TOKEN_RE = re.compile(r"(?<![\w./~-])(scripts/[\w./-]*\.(?:py|sh))")

#: `working-directory` values that still resolve to the repository root.
_ROOT_WORKING_DIRECTORIES = frozenset({"", ".", "./"})


class ScriptReference(NamedTuple):
    """One repo-local script path executed by a workflow `run:` step."""

    workflow: str  # workflow filename the reference appears in
    job: str  # job id the step belongs to
    path: str  # repo-root-relative script path


class SkippedStep(NamedTuple):
    """One `run:` step deliberately not scanned, and why."""

    workflow: str
    job: str
    reason: str


def _is_foreign_root_checkout(step: dict[str, Any]) -> str | None:
    """Return the foreign repo an `actions/checkout` lands at the workspace root.

    A self-checkout omits `repository:`. A step that names one AND does not
    redirect it with a non-root `path:` replaces the workspace root with
    another repo's tree, after which no `scripts/...` path in that job is a
    claim about this repo. No workflow in this tree currently has that shape;
    the former live instance was `cr-thread-gate.yml`, which sparse-checked-out
    `OmniNode-ai/omniclaude` at root to run `scripts/check-unresolved-threads.sh`
    (deleted in OMN-16933). Covered synthetically below.
    """
    uses = step.get("uses")
    if not isinstance(uses, str) or not uses.split("@", 1)[0].endswith(
        "actions/checkout"
    ):
        return None
    with_block = step.get("with")
    if not isinstance(with_block, dict):
        return None
    repository = with_block.get("repository")
    if not isinstance(repository, str) or not repository.strip():
        return None
    path = with_block.get("path")
    if isinstance(path, str) and path.strip() not in _ROOT_WORKING_DIRECTORIES:
        return None
    return repository.strip()


def _strip_full_line_comments(run_body: str) -> str:
    """Drop whole-line shell comments from a `run:` body.

    Only whole-line comments are removed. A trailing `#` is left alone on
    purpose: it can live inside a quoted string or a `${{ }}` expression, and
    mis-stripping it would silently drop a real command from the scan — the
    vacuous-green direction. Over-scanning a comment is the safe error here:
    the worst case is demanding a file that a comment mentioned, which is
    loud and trivially fixed.
    """
    return "\n".join(
        line for line in run_body.splitlines() if not line.lstrip().startswith("#")
    )


def _run_working_directory(
    step: dict[str, Any], job_default: str | None, workflow_default: str | None
) -> str | None:
    """Resolve the effective `working-directory` for one step.

    Precedence is GitHub's: step > `jobs.<id>.defaults.run` > top-level
    `defaults.run`.
    """
    for candidate in (
        step.get("working-directory"),
        job_default,
        workflow_default,
    ):
        if isinstance(candidate, str):
            return candidate
    return None


def _defaults_working_directory(container: Any) -> str | None:
    if not isinstance(container, dict):
        return None
    run_defaults = container.get("defaults")
    if not isinstance(run_defaults, dict):
        return None
    run_section = run_defaults.get("run")
    if not isinstance(run_section, dict):
        return None
    value = run_section.get("working-directory")
    return value if isinstance(value, str) else None


def collect_script_references(
    workflows_dir: Path,
) -> tuple[list[ScriptReference], list[SkippedStep]]:
    """Extract repo-local script references from every workflow in a directory.

    Returns `(references, skipped)`. `skipped` names every `run:` step that was
    deliberately not scanned and the reason, so the gate's blind spots are
    visible on every run instead of silent.
    """
    references: list[ScriptReference] = []
    skipped: list[SkippedStep] = []

    workflow_paths = sorted(workflows_dir.glob("*.yml")) + sorted(
        workflows_dir.glob("*.yaml")
    )
    for workflow_path in workflow_paths:
        loaded = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        jobs = loaded.get("jobs")
        if not isinstance(jobs, dict):
            continue
        workflow_default = _defaults_working_directory(loaded)

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_default = _defaults_working_directory(job)
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue

            foreign_root: str | None = None
            for step in steps:
                if not isinstance(step, dict):
                    continue

                foreign_root = _is_foreign_root_checkout(step) or foreign_root

                run_body = step.get("run")
                if not isinstance(run_body, str):
                    continue

                if foreign_root is not None:
                    skipped.append(
                        SkippedStep(
                            workflow_path.name,
                            str(job_id),
                            f"workspace root replaced by {foreign_root} checkout",
                        )
                    )
                    continue

                working_directory = _run_working_directory(
                    step, job_default, workflow_default
                )
                if (
                    working_directory is not None
                    and working_directory.strip() not in _ROOT_WORKING_DIRECTORIES
                ):
                    skipped.append(
                        SkippedStep(
                            workflow_path.name,
                            str(job_id),
                            f"working-directory={working_directory!r}",
                        )
                    )
                    continue

                for match in _SCRIPT_TOKEN_RE.finditer(
                    _strip_full_line_comments(run_body)
                ):
                    references.append(
                        ScriptReference(
                            workflow=workflow_path.name,
                            job=str(job_id),
                            path=match.group(1),
                        )
                    )

    return references, skipped


def find_missing(
    references: list[ScriptReference], repo_root: Path
) -> list[ScriptReference]:
    """Return the references whose target is not a file in `repo_root`."""
    return [ref for ref in references if not (repo_root / ref.path).is_file()]


# --------------------------------------------------------------------------
# The gate itself
# --------------------------------------------------------------------------


def test_every_workflow_referenced_local_script_exists() -> None:
    """No workflow may execute a repo-local script that is absent from the tree."""
    assert WORKFLOWS_DIR.is_dir(), f"{WORKFLOWS_DIR} does not exist"

    references, _skipped = collect_script_references(WORKFLOWS_DIR)
    missing = find_missing(references, REPO_ROOT)

    assert not missing, (
        "workflow(s) execute repo-local script paths that do not exist in this "
        "tree -- the OMN-16664 shape, where a fanned-out workflow referenced a "
        "script the fan-out never carried and the entrypoint died at "
        "[Errno 2] before deciding anything:\n"
        + "\n".join(
            f"  - {ref.workflow} (job {ref.job}) runs {ref.path}" for ref in missing
        )
        + "\nAdd the script, or change the step to stop claiming it."
    )


def test_repo_workflows_reference_at_least_one_local_script() -> None:
    """Vacuity guard: a silently-broken extractor must not read as green.

    If this repo genuinely stops running any repo-local script from a
    workflow, delete this test along with the module -- do not relax it.
    """
    references, _skipped = collect_script_references(WORKFLOWS_DIR)
    assert references, (
        f"no repo-local script reference found in any workflow under "
        f"{WORKFLOWS_DIR}. Either the extractor has stopped matching (in which "
        f"case the gate above is vacuously green and this is the only signal), "
        f"or this repo no longer runs repo-local scripts from CI."
    )


# --------------------------------------------------------------------------
# Extractor unit tests -- synthetic trees with known answers
# --------------------------------------------------------------------------


def _write_workflow(directory: Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")


def test_extractor_finds_a_root_relative_script(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/ci/precheck.py state.json
""",
    )
    references, skipped = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == ["scripts/ci/precheck.py"]
    assert skipped == []


def test_extractor_finds_shell_scripts_and_multiline_bodies(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          set -euo pipefail
          bash scripts/hooks/prepush.sh
          python3 scripts/ci/one.py && python3 scripts/ci/two.py
""",
    )
    references, _ = collect_script_references(tmp_path)
    assert sorted(ref.path for ref in references) == [
        "scripts/ci/one.py",
        "scripts/ci/two.py",
        "scripts/hooks/prepush.sh",
    ]


def test_extractor_skips_steps_with_a_non_root_working_directory(
    tmp_path: Path,
) -> None:
    """The live omnimarket-checkout shape must not produce a false positive."""
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - working-directory: .occ-autobind-src
        run: python scripts/publish_occ_autobind_command.py --lane dev
""",
    )
    references, skipped = collect_script_references(tmp_path)
    assert references == []
    assert [(s.workflow, s.job) for s in skipped] == [("w.yml", "build")]
    assert ".occ-autobind-src" in skipped[0].reason


def test_extractor_honours_job_and_workflow_run_defaults(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
defaults:
  run:
    working-directory: sub
jobs:
  inherits:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/ci/a.py
  overrides:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: "."
    steps:
      - run: python3 scripts/ci/b.py
""",
    )
    references, skipped = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == ["scripts/ci/b.py"]
    assert [(s.workflow, s.job) for s in skipped] == [("w.yml", "inherits")]
    assert "'sub'" in skipped[0].reason


def test_extractor_skips_a_job_after_a_foreign_root_checkout(tmp_path: Path) -> None:
    """A foreign-root-checkout job must not produce a false positive.

    The job checks another repo out AT THE WORKSPACE ROOT and then runs a
    script from it — a file present at runtime and absent from this tree by
    design. Modelled on the former `cr-thread-gate.yml` shape (deleted in
    OMN-16933); kept synthetic so the guard survives that deletion.
    """
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: OmniNode-ai/omniclaude
          ref: main
          sparse-checkout: scripts/check-unresolved-threads.sh
      - run: bash scripts/check-unresolved-threads.sh owner repo 1
  local:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/ci/mine.py
""",
    )
    references, skipped = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == ["scripts/ci/mine.py"]
    assert [(s.workflow, s.job) for s in skipped] == [("w.yml", "gate")]
    assert "OmniNode-ai/omniclaude" in skipped[0].reason


def test_foreign_checkout_redirected_by_path_does_not_disable_a_job(
    tmp_path: Path,
) -> None:
    """`path:` keeps the workspace root as this repo, so scanning continues.

    This is the OCC shape: omnimarket lands in `.occ-autobind-src`, and the
    precheck step that follows still runs against this repo's tree — which is
    exactly the step OMN-16664 is about, so it must stay in scope.
    """
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  replay:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: OmniNode-ai/omnimarket
          path: .occ-autobind-src
      - run: python3 scripts/ci/occ_manual_replay_precheck.py pr_state.json
""",
    )
    references, skipped = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == [
        "scripts/ci/occ_manual_replay_precheck.py"
    ]
    assert skipped == []


def test_extractor_ignores_prefixed_and_commented_paths(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          # python3 scripts/ci/commented_out.py
          python3 .occ-autobind-src/scripts/ci/other_repo.py
          python3 ../scripts/ci/parent.py
          python3 scripts/ci/real.py
""",
    )
    references, _ = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == ["scripts/ci/real.py"]


def test_extractor_ignores_uses_steps_and_non_string_run(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "w.yml",
        """
name: w
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          sparse-checkout: |
            scripts/ci/not_executed_here.py
      - run: python3 scripts/ci/executed.py
""",
    )
    references, _ = collect_script_references(tmp_path)
    assert [ref.path for ref in references] == ["scripts/ci/executed.py"]


def test_find_missing_reports_absent_targets(tmp_path: Path) -> None:
    (tmp_path / "scripts" / "ci").mkdir(parents=True)
    (tmp_path / "scripts" / "ci" / "present.py").write_text("", encoding="utf-8")
    references = [
        ScriptReference("w.yml", "build", "scripts/ci/present.py"),
        ScriptReference("w.yml", "build", "scripts/ci/absent.py"),
    ]
    assert [ref.path for ref in find_missing(references, tmp_path)] == [
        "scripts/ci/absent.py"
    ]


def test_find_missing_rejects_a_directory_target(tmp_path: Path) -> None:
    """A directory is not a runnable script; `is_file` must not accept it."""
    (tmp_path / "scripts" / "ci" / "precheck.py").mkdir(parents=True)
    references = [ScriptReference("w.yml", "build", "scripts/ci/precheck.py")]
    assert len(find_missing(references, tmp_path)) == 1


# --------------------------------------------------------------------------
# Pre-commit / CLI entrypoint
# --------------------------------------------------------------------------


def _main() -> int:
    """Run the gate outside pytest, for the pre-commit hook and CI job."""
    if not WORKFLOWS_DIR.is_dir():
        print(f"no workflows directory at {WORKFLOWS_DIR}", file=sys.stderr)
        return 2

    references, skipped = collect_script_references(WORKFLOWS_DIR)
    missing = find_missing(references, REPO_ROOT)

    for skip in skipped:
        print(f"skipped: {skip.workflow} job {skip.job} -- {skip.reason}")

    if not references:
        print(
            "REFUSED: no repo-local script reference found in any workflow -- "
            "the extractor may have stopped matching, which would make this "
            "gate vacuously green.",
            file=sys.stderr,
        )
        return 2

    if missing:
        print(
            "REFUSED: workflow(s) execute repo-local script paths absent from "
            "this tree (OMN-16664):",
            file=sys.stderr,
        )
        for ref in missing:
            print(
                f"  - {ref.workflow} (job {ref.job}) runs {ref.path}", file=sys.stderr
            )
        return 1

    print(
        f"OK: {len(references)} workflow-referenced repo-local script path(s) "
        f"all exist ({len(skipped)} step(s) out of scope, listed above)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
