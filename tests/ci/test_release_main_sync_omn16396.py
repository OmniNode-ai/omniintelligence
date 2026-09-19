# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""`release.yml` must fast-forward `main` to the released tag (OMN-16396).

omni_home's Release-Synced `main` policy lists this repository with an ACTIVE
ruleset (21865240, `update` + `non_fast_forward`, sole bypass actor
`Integration:4361937` = onexbot-occ-writer) and an empty
`required_status_checks.contexts` on `main`. Both halves are the invariant and
neither alone is sufficient: the ruleset's whole premise is that a release
publishes and then `release.yml` moves the pointer. Without the pointer move the
ruleset does not protect the release boundary, it FREEZES it -- `main` stops
advancing and every consumer that reads `main` reads a stale tree, silently,
with nothing failing.

That is not hypothetical here. Measured 2026-09-19, before this job existed:
`main` sat at 2026-08-22, 75 commits behind `dev`, 0 ahead. The identical
condition on omnidash (OMN-16396, omnidash#322) is what made a CVE fix that had
landed on `dev` invisible to an image scanner that reads `main`.

So the properties below are asserted over the PARSED workflow rather than over a
diff: an edit that drops any of them fails here instead of passing review
unnoticed. They are separate tests because they fail separately, and several of
them fail SILENTLY in production -- a job that mints the wrong identity, or
falls back to the workflow token, still reports success while `main` never
moves.

Shape and precedent: omnibase_core's `sync-main` job and omnidash#322, under
OMN-16289 / OMN-16396.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RELEASE = WORKFLOWS / "release.yml"
SYNC_JOB = "sync-main"

MAIN_REF_PATH = "git/refs/heads/main"


def _workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(RELEASE.read_text(encoding="utf-8")))


def _job() -> dict[str, Any]:
    jobs = _workflow().get("jobs", {})
    assert SYNC_JOB in jobs, (
        f"{RELEASE.name}: job {SYNC_JOB!r} not found; jobs={sorted(jobs)}. The "
        "release-synced main policy lists this repository with an active ruleset "
        "whose only premise is that this job exists. Without it the ruleset "
        "freezes `main` rather than protecting it (OMN-16396)."
    )
    return dict(jobs[SYNC_JOB])


def _steps() -> list[dict[str, Any]]:
    return list(_job().get("steps", []) or [])


def _step_text() -> str:
    return "\n".join(
        yaml.safe_dump(step, default_flow_style=False) for step in _steps()
    )


def _run_scripts() -> list[tuple[str, str]]:
    return [
        (str(step.get("name") or step.get("id") or "<unnamed>"), str(step["run"]))
        for step in _steps()
        if "run" in step
    ]


def _script_text() -> str:
    """The committed shell, UNESCAPED.

    `_step_text` round-trips through `yaml.safe_dump`, which escapes the double
    quotes inside a run block -- so a literal JSON fragment such as
    `{"force":false}` does not appear in it verbatim. Assertions about what the
    shell SAYS read this; assertions about the YAML structure (`uses`, `with`,
    `if`) read `_step_text`.
    """
    return "\n".join(script for _, script in _run_scripts())


def test_the_sync_job_is_real_and_moves_the_main_ref() -> None:
    """Positive control for every assertion in this file.

    All of them read this job's own steps. A job that delegates to a reusable
    workflow has no steps at all, and each assertion below would then pass over an
    empty string -- reporting green on the precise defect this file exists to
    catch.
    """
    steps = _steps()
    assert steps, (
        f"{RELEASE.name}:{SYNC_JOB} declares no steps, so it delegates elsewhere "
        "and every assertion in this file would pass vacuously."
    )
    text = _script_text()
    assert MAIN_REF_PATH in text, (
        f"{RELEASE.name}:{SYNC_JOB} never references {MAIN_REF_PATH!r}, so this "
        "file is no longer asserting anything about how `main` is advanced."
    )
    assert "PATCH" in text, (
        f"{RELEASE.name}:{SYNC_JOB} issues no PATCH; the ref is not being moved "
        "over REST any more and the identity guarantees below do not apply."
    )


def test_sync_runs_only_after_a_successful_non_rc_release() -> None:
    """A pointer move off a failed publish, or onto a prerelease, is not a release.

    `needs.release.result == 'success'` is explicit rather than implied so that a
    future sync-only dispatch path cannot run off an empty version string.
    """
    job = _job()
    assert job.get("needs") == "release" or "release" in (job.get("needs") or []), (
        f"{RELEASE.name}:{SYNC_JOB} does not depend on the `release` job, so it "
        "could move `main` to a tag that never published."
    )
    condition = str(job.get("if", ""))
    assert "needs.release.result == 'success'" in condition, (
        f"{RELEASE.name}:{SYNC_JOB} does not require `release` to have SUCCEEDED. "
        f"Its condition is {condition!r}. A skipped or failed publish must never "
        "advance the release pointer."
    )
    assert "rc" in condition, (
        f"{RELEASE.name}:{SYNC_JOB} does not exclude rc tags; its condition is "
        f"{condition!r}. `main` is the last RELEASE, not the last prerelease."
    )


def test_sync_checks_out_without_persisting_credentials() -> None:
    """Leave no persisted workflow token that could override the App identity.

    Omitting the flag is not a weaker version of the fix. `actions/checkout` v7
    writes the workflow token's basic-auth extraheader into a separate file and
    includes it through `includeIf.gitdir`, and that header overrides any
    credential written into a remote URL -- so the job silently acts as
    github-actions[bot], which is NOT a bypass actor for the `main` ruleset.
    """
    checkouts = [
        step
        for step in _steps()
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, (
        f"{RELEASE.name}:{SYNC_JOB} runs no actions/checkout, so it cannot resolve "
        "the ancestry preconditions below and this assertion cannot mean anything."
    )
    for step in checkouts:
        with_block = step.get("with") or {}
        assert with_block.get("persist-credentials") is False, (
            f"{RELEASE.name}:{SYNC_JOB} checks out without "
            "`persist-credentials: false`."
        )
        assert with_block.get("fetch-depth") == 0, (
            f"{RELEASE.name}:{SYNC_JOB} checks out shallow. The ancestry guards "
            "need full history or `merge-base --is-ancestor` answers about a "
            "truncated graph."
        )


def test_sync_mints_the_app_token_fail_closed() -> None:
    """An unmintable token must stop the move rather than degrade it.

    The ruleset's only bypass actor is the onexbot-occ-writer App. A fallback to
    the workflow token does not make the push work -- it makes it fail as GH013
    while some other step still reports success, which is how a desync goes
    unnoticed.
    """
    text = _step_text()

    assert "actions/create-github-app-token" in text, (
        f"{RELEASE.name}:{SYNC_JOB} moves a restricted ref but never mints an App "
        "installation token."
    )
    assert re.search(r"secrets\.ONEXBOT_OCC_APP_ID\b", text) is not None, (
        f"{RELEASE.name}:{SYNC_JOB} does not mint from ONEXBOT_OCC_APP_ID."
    )
    assert re.search(r"secrets\.ONEXBOT_OCC_PRIVATE_KEY\b", text) is not None, (
        f"{RELEASE.name}:{SYNC_JOB} does not mint from ONEXBOT_OCC_PRIVATE_KEY."
    )

    fallback = re.search(
        r"steps\.[\w-]+\.outputs\.token\s*\|\|\s*secrets\.GITHUB_TOKEN", text
    )
    assert fallback is None, (
        f"{RELEASE.name}:{SYNC_JOB} falls back to secrets.GITHUB_TOKEN when the "
        "mint fails."
    )
    # Broader than the fallback expression: the default token must not be
    # reachable from this job in any form. Comments are dropped by the YAML load,
    # so prose explaining the prohibition cannot trip this.
    assert "secrets.GITHUB_TOKEN" not in text, (
        f"{RELEASE.name}:{SYNC_JOB} references secrets.GITHUB_TOKEN. The ref move "
        "must have no route back to the workflow token."
    )
    assert "github.token" not in text, (
        f"{RELEASE.name}:{SYNC_JOB} references github.token -- the same failure, "
        "spelled the other way."
    )


def test_sync_mints_both_required_permission_scopes() -> None:
    """A `permission-*` input REPLACES the installation's full set.

    Listing `workflows` alone silently drops `contents`, so the minted token
    cannot move ANY ref and the fast-forward dies on GH013 (omnibase_core run
    34065670492, OMN-17272). Both are required: contents to move the ref at all,
    workflows because a release tag can legitimately contain changes under
    .github/workflows/.
    """
    mints = [
        step
        for step in _steps()
        if str(step.get("uses", "")).startswith("actions/create-github-app-token")
    ]
    assert mints, f"{RELEASE.name}:{SYNC_JOB} mints no App token."
    for step in mints:
        with_block = step.get("with") or {}
        assert with_block.get("permission-contents") == "write", (
            f"{RELEASE.name}:{SYNC_JOB} does not mint `permission-contents: write`, "
            "so the token cannot move refs/heads/main at all."
        )
        assert with_block.get("permission-workflows") == "write", (
            f"{RELEASE.name}:{SYNC_JOB} does not mint `permission-workflows: "
            "write`, so a release tag touching .github/workflows/ is refused."
        )


def test_the_ref_update_is_never_forced() -> None:
    """`"force": false` puts GitHub's own fast-forward check under this job's.

    The workflow's ancestry precondition names WHY a bad move is refused; the
    server-side guard is what still holds if that precondition is ever wrong.
    """
    text = _script_text()
    assert '"force":false' in text.replace(" ", ""), (
        f'{RELEASE.name}:{SYNC_JOB} does not send `"force": false` with the ref '
        "update. Without it a non-fast-forward would DISCARD commits that are on "
        "`main` and nowhere else."
    )
    assert '"force":true' not in text.replace(" ", ""), (
        f"{RELEASE.name}:{SYNC_JOB} forces the ref update."
    )
    assert "--force" not in text and "force-with-lease" not in text, (
        f"{RELEASE.name}:{SYNC_JOB} contains a force push flag."
    )


def test_the_fast_forward_is_guarded_in_both_directions() -> None:
    """Refuse a tag that is not cut from dev, and refuse to move main backwards."""
    text = _script_text()
    assert text.count("merge-base --is-ancestor") >= 2, (
        f"{RELEASE.name}:{SYNC_JOB} carries fewer than two ancestry checks. Both "
        "are needed: the tag must descend from `dev` (it is a release cut, not an "
        "arbitrary commit), and `main` must be an ancestor of the tag (never "
        "backwards, never sideways)."
    )
    assert "origin/dev" in text, (
        f"{RELEASE.name}:{SYNC_JOB} never resolves origin/dev, so it cannot check "
        "that the tag is a cut from dev."
    )
    assert "origin/main" in text, (
        f"{RELEASE.name}:{SYNC_JOB} never resolves origin/main, so it cannot check "
        "that the move is a fast-forward."
    )


def test_the_move_is_read_back() -> None:
    """A 2xx on the PATCH is not proof the pointer moved.

    That is the failure mode the OMN-16343 GH006 incident turned on: the ref read
    back correctly in one surface while the push had been declined in another.
    """
    text = _script_text()
    assert "git/ref/heads/main" in text, (
        f"{RELEASE.name}:{SYNC_JOB} never reads `main` back after the update, so a "
        "sync that did not land would report success."
    )
    assert "did not land" in text, (
        f"{RELEASE.name}:{SYNC_JOB} has no readback comparison that fails loudly."
    )


def test_the_sync_job_mutates_nothing_but_this_repository_s_main() -> None:
    """Blast radius, asserted rather than intended.

    This job exists to move one pointer. A dispatch to another repository, or
    anything that can reach a cluster, would inherit a release-time trigger that
    nothing else gates.
    """
    text = _step_text()
    for forbidden in (
        "repository-dispatch",
        "kubectl",
        "aws ",
        "uv publish",
        "docker ",
        "workflow_dispatch",
    ):
        assert forbidden not in text, (
            f"{RELEASE.name}:{SYNC_JOB} contains {forbidden!r}. This job must "
            "perform exactly one mutation: the REST update of refs/heads/main in "
            "this repository."
        )
    other_repo_writes = re.findall(r"repos/(?!\$\{)([\w.-]+/[\w.-]+)", text)
    assert not other_repo_writes, (
        f"{RELEASE.name}:{SYNC_JOB} names other repositories literally in API "
        f"paths: {sorted(set(other_repo_writes))}. It must act only on "
        "${GITHUB_REPOSITORY}."
    )


def test_every_run_script_is_valid_shell() -> None:
    """Parse the committed shell, so a syntax error fails here and not at release.

    These scripts run once per release cut. A `bash -n` failure discovered then is
    discovered on the one path that has no dry run.
    """
    for name, script in _run_scripts():
        proc = subprocess.run(
            ["bash", "-n"],
            input=script,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, (
            f"{RELEASE.name}:{SYNC_JOB} step {name!r} is not valid shell:\n"
            f"{proc.stderr}"
        )


def test_the_validation_shell_carries_no_inline_expressions() -> None:
    """Values arrive through `env:` so the committed shell is executable verbatim.

    An inline `${{ }}` interpolates attacker-influenceable text straight into the
    script, and it also makes the block untestable as written -- which is what
    `test_every_run_script_is_valid_shell` above depends on.
    """
    offenders = [name for name, script in _run_scripts() if "${{" in script]
    assert not offenders, (
        f"{RELEASE.name}:{SYNC_JOB} steps {offenders} interpolate `${{{{ }}}}` "
        "inline. Pass the value through `env:` instead."
    )
