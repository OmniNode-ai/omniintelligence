# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Fail-closed gate: CI's full-suite branch must be a superset of its narrowed branch.

OMN-18578 (root cause). `ci.yml`'s `test-unit` job has two mutually exclusive
pytest steps. The narrowed one runs whatever `scripts/ci/detect_test_paths.py`
selected. The escalating one — "Run unit tests (full suite)", the branch taken
whenever the selector decides narrowing cannot be proven safe — ran a
hardcoded two-path subset:

    uv run pytest tests/unit/tools/ tests/unit/scripts/test_validate_no_env_fallbacks.py

That is 10 of the repo's 361 test files. The narrowed branch's own fallback,
when a diff maps to no module, is the whole of `tests/unit/` (306 files). So
the escalation path was NARROWER than the path it escalates from, and setting
`ENABLE_SMART_TESTS` to anything but `true` — the documented safe fallback in
every other repo in the fleet — shrank coverage instead of widening it.

Measured before the fix, run 31811881504 job 94804418096, the step's own log:

    collected 236 items / 212 deselected / 24 selected
    24 passed, 212 deselected in 10.05s

236 items is the whole escalation denominator across all ten splits. The tree
the selector's `_full_suite()` actually names — `selected_paths=["tests/"]` —
collects 5,949.

Nothing detected this, because nothing read the workflow. This module reads it.

## What is asserted

Statically, from parsed YAML plus the selector's own code — no network, no
token, no runner:

* the full-suite step selects the root the selector's full-set output names;
* EVERY `EnumFullSuiteReason` produces a selection the full-suite step's own
  pytest arguments cover, so adding an eighth reason that routes elsewhere is
  a red test rather than a review catch;
* `test-unit` and its selector job cannot be skipped on `pull_request` or
  `merge_group`;
* the coverage flag covers the package, not one subpackage of it;
* the two steps exclude exactly the same paths, so "superset" is a claim about
  what actually executes rather than about the argument list.

## What is deliberately NOT asserted, and why

* **That `tests/integration/` runs.** Those tests need a broker and a database
  the job does not provision, and the narrowed branch has always passed
  `--ignore=tests/integration`. The superset invariant is therefore "covers
  everything the selector can narrow TO", and `_resolve` only ever emits
  `tests/unit/<module>/` — never an integration path. Demanding integration
  here would make the gate fail for a reason unrelated to selection, which is
  how gates get disabled.
* **That the tests pass.** Shape only. Whether the suite is green is the
  suite's own job.

This check is check-only. It never rewrites the workflow; it fails and names
the file.
"""

from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.detect_test_paths import (  # noqa: E402
    compute_selection,
)
from scripts.ci.test_selection_models import (  # noqa: E402
    EnumFullSuiteReason,
    ModelTestSelection,
)

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ADJACENCY_PATH = REPO_ROOT / "scripts" / "ci" / "test_selection_adjacency.yaml"

TEST_JOB = "test-unit"
SELECTOR_JOB = "detect-changes"
FULL_SUITE_STEP = "Run unit tests (full suite)"
NARROWED_STEP = "Run unit tests (smart selection)"

#: The package the coverage flag must cover. A subpackage of it is the defect.
EXPECTED_COV_TARGET = "src/omniintelligence"

#: Events on which the test job must never be skipped, whatever the diff is.
UNSKIPPABLE_EVENTS = ("pull_request", "merge_group")

#: A GitHub Actions `${{ ... }}` expression. Collapsed to one opaque token
#: before tokenising, so an expression used as an option value (`--splits ${{
#: ... }}`) does not shatter into several words and leak its fragments into
#: the positional-path list.
GHA_EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)
GHA_EXPRESSION_TOKEN = "GHA_EXPR"


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PytestInvocation:
    """The parts of a `uv run pytest ...` step this gate reasons about."""

    positional_paths: tuple[str, ...]
    ignored_paths: tuple[str, ...]
    cov_targets: tuple[str, ...]


def load_workflow(path: Path = WORKFLOW_PATH) -> dict:
    """Parse the CI workflow. Raises rather than returning a partial mapping."""
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or "jobs" not in parsed:
        raise ValueError(f"{path} does not parse as a workflow with a jobs mapping")
    return parsed


def find_job(workflow: dict, job_id: str) -> dict:
    jobs = workflow["jobs"]
    if job_id not in jobs:
        raise KeyError(f"{WORKFLOW_PATH}: no job '{job_id}'")
    return jobs[job_id]


def find_step(job: dict, step_name: str) -> dict:
    for step in job.get("steps", []):
        if step.get("name") == step_name:
            return step
    raise KeyError(f"{WORKFLOW_PATH}: no step named '{step_name}'")


def parse_pytest_invocation(step: dict) -> PytestInvocation:
    """Extract the pytest paths, ignores and coverage targets from a run step.

    Only the `pytest` command inside the step's `run:` block is read. Shell
    line continuations are folded first so a multi-line invocation parses as
    one command, which is how every such step in this workflow is written.
    """
    run_block = step.get("run")
    if not isinstance(run_block, str):
        raise ValueError(f"step '{step.get('name')}' has no run: block")

    folded = GHA_EXPRESSION.sub(GHA_EXPRESSION_TOKEN, run_block.replace("\\\n", " "))
    pytest_line = next(
        (line for line in folded.splitlines() if " pytest " in f" {line} "),
        None,
    )
    if pytest_line is None:
        raise ValueError(f"step '{step.get('name')}' runs no pytest command")

    tokens = shlex.split(pytest_line)
    try:
        start = tokens.index("pytest") + 1
    except ValueError as exc:  # pragma: no cover - guarded by the check above
        raise ValueError(f"step '{step.get('name')}' runs no pytest command") from exc

    positional: list[str] = []
    ignored: list[str] = []
    cov: list[str] = []

    index = start
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--ignore="):
            ignored.append(token.split("=", 1)[1])
        elif token == "--ignore":
            index += 1
            ignored.append(tokens[index])
        elif token.startswith("--cov="):
            cov.append(token.split("=", 1)[1])
        elif token.startswith("-"):
            # Options that consume a following value. Anything else is a flag,
            # and a flag's value never looks like a path in this workflow.
            if token in {"--splits", "--group", "--junitxml", "--tb", "-m", "-k"}:
                index += 1
        elif token != GHA_EXPRESSION_TOKEN:
            positional.append(token)
        index += 1

    return PytestInvocation(
        positional_paths=tuple(positional),
        ignored_paths=tuple(ignored),
        cov_targets=tuple(cov),
    )


def _as_prefix(path: str) -> str:
    """Normalise a path to a directory prefix form for containment tests."""
    return path if path.endswith("/") else f"{path}/"


def covers(invocation: PytestInvocation, selected_path: str) -> bool:
    """Would running `invocation` execute everything under `selected_path`?

    True when some positional argument is `selected_path` itself or a parent
    directory of it, and no `--ignore` prunes it or any ancestor of it.
    """
    target = _as_prefix(selected_path)

    for ignored in invocation.ignored_paths:
        pruned = _as_prefix(ignored)
        if target == pruned or target.startswith(pruned):
            return False

    for candidate in invocation.positional_paths:
        root = _as_prefix(candidate)
        if target == root or target.startswith(root):
            return True
    return False


# --------------------------------------------------------------------------
# Driving every escalation reason through the real selector
# --------------------------------------------------------------------------


def selection_for_reason(reason: EnumFullSuiteReason) -> ModelTestSelection:
    """Return the selector's real output for the given escalation reason.

    Each case drives `compute_selection` with inputs that produce exactly that
    reason, so this is the selector's own behaviour and not a restatement of
    it. A reason with no case here fails loudly — which is the point: an
    eighth member of the enum must be wired deliberately.
    """
    if reason is EnumFullSuiteReason.FEATURE_FLAG_OFF:
        return compute_selection(
            changed_files=["README.md"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
            feature_flag_enabled=False,
        )
    if reason is EnumFullSuiteReason.MAIN_BRANCH:
        return compute_selection(
            changed_files=["README.md"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="main",
        )
    if reason is EnumFullSuiteReason.MERGE_GROUP:
        return compute_selection(
            changed_files=["README.md"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
            event_name="merge_group",
        )
    if reason is EnumFullSuiteReason.SCHEDULED:
        return compute_selection(
            changed_files=["README.md"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
            event_name="schedule",
        )
    if reason is EnumFullSuiteReason.TEST_INFRASTRUCTURE:
        return compute_selection(
            changed_files=["tests/conftest.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
        )
    if reason is EnumFullSuiteReason.SHARED_MODULE:
        return compute_selection(
            changed_files=["src/omniintelligence/models/model_anything.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
        )
    if reason is EnumFullSuiteReason.THRESHOLD_MODULES:
        return compute_selection(
            changed_files=[
                f"src/omniintelligence/{module}/thing.py"
                for module in (
                    "api",
                    "audit",
                    "debug_intel",
                    "mismatch_detector",
                    "review_bot",
                    "rl",
                )
            ],
            adjacency_path=ADJACENCY_PATH,
            ref_name="dev",
        )
    raise AssertionError(
        f"{reason} has no case in selection_for_reason -- a new escalation "
        "reason must be wired into this gate deliberately (OMN-18578)"
    )


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict:
    return load_workflow()


@pytest.fixture(scope="module")
def full_suite(workflow: dict) -> PytestInvocation:
    return parse_pytest_invocation(
        find_step(find_job(workflow, TEST_JOB), FULL_SUITE_STEP)
    )


@pytest.fixture(scope="module")
def narrowed(workflow: dict) -> PytestInvocation:
    return parse_pytest_invocation(
        find_step(find_job(workflow, TEST_JOB), NARROWED_STEP)
    )


@pytest.mark.unit
def test_full_suite_step_selects_the_tree_the_selector_names(
    full_suite: PytestInvocation,
) -> None:
    """The escalation branch runs the root `_full_suite()` names, not a subset."""
    assert "tests/" in {_as_prefix(p) for p in full_suite.positional_paths}, (
        f"{WORKFLOW_PATH}: step '{FULL_SUITE_STEP}' selects "
        f"{list(full_suite.positional_paths)}, not the 'tests/' root that "
        "scripts/ci/detect_test_paths.py:_full_suite names (OMN-18578)"
    )


@pytest.mark.unit
@pytest.mark.parametrize("reason", list(EnumFullSuiteReason))
def test_every_escalation_reason_lands_on_a_covered_selection(
    reason: EnumFullSuiteReason, full_suite: PytestInvocation
) -> None:
    """Each reason's real selection must be executed by the full-suite step."""
    selection = selection_for_reason(reason)
    assert selection.is_full_suite is True
    assert selection.full_suite_reason == reason

    uncovered = [p for p in selection.selected_paths if not covers(full_suite, p)]
    assert not uncovered, (
        f"{WORKFLOW_PATH}: escalation reason '{reason.value}' selects "
        f"{uncovered}, which step '{FULL_SUITE_STEP}' does not run (OMN-18578)"
    )


@pytest.mark.unit
def test_full_suite_covers_everything_the_narrowed_branch_can_select(
    full_suite: PytestInvocation,
) -> None:
    """Superset invariant, over every unit test directory the selector can emit."""
    narrowable = [
        f"tests/unit/{child.name}/"
        for child in sorted((REPO_ROOT / "tests" / "unit").iterdir())
        if child.is_dir() and not child.name.startswith("__")
    ]
    assert narrowable, "positive control: tests/unit has no subdirectories to narrow to"

    uncovered = [path for path in narrowable if not covers(full_suite, path)]
    assert not uncovered, (
        f"{WORKFLOW_PATH}: step '{FULL_SUITE_STEP}' does not run {uncovered}, "
        f"which step '{NARROWED_STEP}' can select (OMN-18578)"
    )


@pytest.mark.unit
def test_both_branches_exclude_the_same_paths(
    full_suite: PytestInvocation, narrowed: PytestInvocation
) -> None:
    """A wider argument list with a wider --ignore is not a superset."""
    assert set(full_suite.ignored_paths) == set(narrowed.ignored_paths), (
        f"{WORKFLOW_PATH}: '{FULL_SUITE_STEP}' ignores "
        f"{sorted(full_suite.ignored_paths)} but '{NARROWED_STEP}' ignores "
        f"{sorted(narrowed.ignored_paths)} -- the two must prune identically "
        "or 'superset' is an argument-list claim, not an execution claim"
    )


@pytest.mark.unit
def test_full_suite_coverage_is_scoped_to_the_whole_package(
    full_suite: PytestInvocation,
) -> None:
    """`--cov` on a subpackage under-reports a run of the whole tree."""
    assert list(full_suite.cov_targets) == [EXPECTED_COV_TARGET], (
        f"{WORKFLOW_PATH}: step '{FULL_SUITE_STEP}' measures coverage of "
        f"{list(full_suite.cov_targets)}, not {EXPECTED_COV_TARGET} (OMN-18578)"
    )


@pytest.mark.unit
@pytest.mark.parametrize("job_id", [TEST_JOB, SELECTOR_JOB])
def test_test_jobs_are_not_path_filtered_away(workflow: dict, job_id: str) -> None:
    """Neither the selector nor the test job may be skipped by a path filter.

    A diff touching `src/omniintelligence/nodes/**` matched no entry in the
    `production_code` filter, so the whole test job was skipped and `CI
    Summary` recorded it as "skipped by policy". Measured on 3 of the last 8
    pull-request runs before this gate landed.
    """
    condition = str(find_job(workflow, job_id).get("if", ""))
    assert "production_code" not in condition, (
        f"{WORKFLOW_PATH}: job '{job_id}' is gated on the production_code path "
        f"filter (if: {condition!r}), so a diff outside that filter runs no "
        f"tests at all on {' or '.join(UNSKIPPABLE_EVENTS)} (OMN-18578)"
    )


@pytest.mark.unit
def test_narrowed_step_consumes_the_selector_output(workflow: dict) -> None:
    """Positive control: the narrowed branch really is selector-driven.

    Without this, a workflow that hardcoded both branches identically would
    satisfy every superset assertion above while running no selection at all.
    """
    step = find_step(find_job(workflow, TEST_JOB), NARROWED_STEP)
    assert "selected_paths" in step["run"], (
        f"{WORKFLOW_PATH}: step '{NARROWED_STEP}' does not read the selector's "
        "selected_paths output -- the smart branch is not selector-driven"
    )


# --------------------------------------------------------------------------
# Self-tests for the helpers (so a silently-broken parser cannot pass the gate)
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_covers_rejects_the_pre_fix_argument_list() -> None:
    """Positive control: the shape this gate exists to refuse must not pass."""
    pre_fix = PytestInvocation(
        positional_paths=(
            "tests/unit/tools/",
            "tests/unit/scripts/test_validate_no_env_fallbacks.py",
        ),
        ignored_paths=(),
        cov_targets=("src/omniintelligence/validators",),
    )
    assert not covers(pre_fix, "tests/")
    assert not covers(pre_fix, "tests/unit/nodes/")
    assert covers(pre_fix, "tests/unit/tools/")


@pytest.mark.unit
def test_covers_honours_an_ignore_that_prunes_the_target() -> None:
    invocation = PytestInvocation(
        positional_paths=("tests/",),
        ignored_paths=("tests/integration",),
        cov_targets=(),
    )
    assert covers(invocation, "tests/unit/nodes/")
    assert not covers(invocation, "tests/integration/")
    assert not covers(invocation, "tests/integration/nodes/")


@pytest.mark.unit
def test_parse_pytest_invocation_folds_line_continuations() -> None:
    step = {
        "name": "example",
        "run": (
            "uv run pytest tests/ \\\n"
            "  --ignore=tests/integration \\\n"
            "  --splits 10 \\\n"
            "  --group 3 \\\n"
            "  --cov=src/omniintelligence \\\n"
            "  --junitxml=junit.xml\n"
        ),
    }
    parsed = parse_pytest_invocation(step)
    assert parsed.positional_paths == ("tests/",)
    assert parsed.ignored_paths == ("tests/integration",)
    assert parsed.cov_targets == ("src/omniintelligence",)


@pytest.mark.unit
def test_parse_pytest_invocation_folds_actions_expressions() -> None:
    """A `${{ ... }}` option value must not shatter into positional paths."""
    step = {
        "name": "example",
        "run": (
            "uv run pytest tests/ \\\n"
            "  --splits ${{ needs.detect-changes.outputs.split_count }} \\\n"
            "  --group ${{ matrix.split }} \\\n"
            "  --junitxml=junit-unit-${{ matrix.split }}.xml\n"
        ),
    }
    assert parse_pytest_invocation(step).positional_paths == ("tests/",)


@pytest.mark.unit
def test_selection_for_reason_covers_every_enum_member() -> None:
    """An eighth escalation reason must be wired here, not silently skipped."""
    for reason in EnumFullSuiteReason:
        selection = selection_for_reason(reason)
        assert selection.full_suite_reason == reason


# --------------------------------------------------------------------------
# Pre-commit / CLI entrypoint
# --------------------------------------------------------------------------


def _main() -> int:
    """Run the gate outside pytest, for the pre-commit hook and the CI job."""
    if not WORKFLOW_PATH.is_file():
        print(f"REFUSED: no workflow at {WORKFLOW_PATH}", file=sys.stderr)
        return 2

    try:
        parsed = load_workflow()
        job = find_job(parsed, TEST_JOB)
        full = parse_pytest_invocation(find_step(job, FULL_SUITE_STEP))
        narrow = parse_pytest_invocation(find_step(job, NARROWED_STEP))
    except (KeyError, ValueError) as exc:
        print(f"REFUSED: {WORKFLOW_PATH}: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []

    if "tests/" not in {_as_prefix(p) for p in full.positional_paths}:
        failures.append(
            f"step '{FULL_SUITE_STEP}' selects {list(full.positional_paths)}, "
            "not the 'tests/' root the selector's full-set output names"
        )

    for reason in EnumFullSuiteReason:
        try:
            selection = selection_for_reason(reason)
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        uncovered = [p for p in selection.selected_paths if not covers(full, p)]
        if uncovered:
            failures.append(
                f"escalation reason '{reason.value}' selects {uncovered}, "
                f"which step '{FULL_SUITE_STEP}' does not run"
            )

    if set(full.ignored_paths) != set(narrow.ignored_paths):
        failures.append(
            f"'{FULL_SUITE_STEP}' ignores {sorted(full.ignored_paths)} but "
            f"'{NARROWED_STEP}' ignores {sorted(narrow.ignored_paths)}"
        )

    if list(full.cov_targets) != [EXPECTED_COV_TARGET]:
        failures.append(
            f"step '{FULL_SUITE_STEP}' measures coverage of "
            f"{list(full.cov_targets)}, not {EXPECTED_COV_TARGET}"
        )

    for job_id in (TEST_JOB, SELECTOR_JOB):
        condition = str(find_job(parsed, job_id).get("if", ""))
        if "production_code" in condition:
            failures.append(
                f"job '{job_id}' is gated on the production_code path filter "
                f"(if: {condition!r}), so a diff outside it runs no tests"
            )

    if failures:
        print(
            f"REFUSED: {WORKFLOW_PATH.relative_to(REPO_ROOT)} escalates to a "
            "test selection narrower than it can narrow to (OMN-18578):",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(
        f"OK: {WORKFLOW_PATH.relative_to(REPO_ROOT)} full-suite branch covers "
        f"all {len(list(EnumFullSuiteReason))} escalation reasons and every "
        "selectable unit test directory."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
