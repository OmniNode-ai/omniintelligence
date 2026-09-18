# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The release tag must be pushed with an identity `release.yml` can hear (OMN-18662).

`release.yml`'s only automatic trigger is `push: tags:`. A push made with the job's
default workflow token delivers no push event, so a tag pushed that way is not
merely mis-attributed -- it is unconsumable, and it cannot be re-pushed without
deleting it first. Every cut then needs a hand `workflow_dispatch`. This
repository's tagger delegated to omnibase_core's shared `auto-tag-reusable.yml`,
which pushes exactly that way, until OMN-18662 inlined it here.

An App-token push DOES start push-driven CI in this org. The proof is a live run,
``omnibase_spi`` ``35134173847`` (`event: push`, `actor: onexbot-occ-writer[bot]`,
`conclusion: success`), which corrected the earlier org-wide belief that App tokens
were suppressed the same way. That belief was a credential confound, not a platform
behaviour: a default ``actions/checkout`` persists a basic-auth
``http.<origin>.extraheader`` carrying the workflow token, and that header overrides
any credential written into the remote URL.

So the property is TWO conditions, and both belong to the job rather than to the
token:

1. the checkout does not persist credentials;
2. the mint fails closed, with no expression anywhere in the job that routes back to
   the default token.

They are asserted separately because they fail separately, and a job that gets
either half wrong pushes as the workflow token while still reporting success --
which is exactly how the wrong finding survived three weeks.

These are asserted over the PARSED workflow, not over a diff, so a later edit that
drops either half fails here rather than passing review unnoticed. The first test is
a positive control: every other assertion reads the job's steps, and a job that
delegates has no steps, so without it they would all pass over the precise defect
this file exists to catch.

Shape and precedent: omnibase_core#1703 and omnibase_spi#308, under OMN-18658.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TAGGER = WORKFLOWS / "auto-tag-on-merge.yml"
TAGGER_JOB = "auto-tag"

APP_BOT_NAME = "onexbot-occ-writer[bot]"
APP_BOT_EMAIL = "307849072+onexbot-occ-writer[bot]@users.noreply.github.com"


def _job() -> dict[str, Any]:
    data = yaml.safe_load(TAGGER.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    assert TAGGER_JOB in jobs, (
        f"{TAGGER.name}: job {TAGGER_JOB!r} not found; jobs={sorted(jobs)}. Either "
        "the tagger moved or it went back to delegating, and in both cases every "
        "assertion below would otherwise pass vacuously."
    )
    return dict(jobs[TAGGER_JOB])


def _steps() -> list[dict[str, Any]]:
    return list(_job().get("steps", []) or [])


def _step_text() -> str:
    return "\n".join(
        yaml.safe_dump(step, default_flow_style=False) for step in _steps()
    )


def test_the_tagger_is_a_real_job_that_pushes_a_tag() -> None:
    """Positive control for every assertion in this file.

    All of them read the tagger's own steps. If the job delegates to a reusable
    workflow it has no steps at all, and each assertion below would pass over an
    empty string -- reporting green on the precise defect this file exists to
    catch.
    """
    steps = _steps()
    assert steps, (
        f"{TAGGER.name}:{TAGGER_JOB} declares no steps, so it delegates to a "
        "reusable workflow. The tagger was inlined under OMN-18662 because the "
        "shared reusable is pinned at a ref on a release-synced main, so a fix "
        "there is not live for the next cut."
    )
    text = _step_text()
    assert "git push" in text, (
        f"{TAGGER.name}:{TAGGER_JOB} contains no `git push`, so this file is no "
        "longer asserting anything about how the release tag reaches the remote."
    )
    assert "git tag" in text, (
        f"{TAGGER.name}:{TAGGER_JOB} no longer creates a tag; the assertions below "
        "would be about a job that does something else entirely."
    )


def test_no_workflow_delegates_tagging_to_the_pinned_reusable() -> None:
    """The inlining has to stay inlined.

    Re-pointing any caller at `auto-tag-reusable.yml` puts the tag push back on the
    workflow token, and every other test here would still pass because they read
    only this one job.
    """
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "auto-tag-reusable.yml@" in stripped:
                offenders.append(path.name)
                break
    assert not offenders, (
        f"{offenders} call auto-tag-reusable.yml. That file pushes the tag with the "
        "workflow token, which delivers no push event, so release.yml would not "
        "start and the cut would need a hand dispatch again (OMN-18662)."
    )


def test_tagger_checks_out_without_persisting_credentials() -> None:
    """Condition 1: leave no persisted workflow token to override the App one.

    Omitting the flag is not a weaker version of the fix -- it defeats it entirely,
    silently, while the job still reports success.
    """
    checkouts = [
        step
        for step in _steps()
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, (
        f"{TAGGER.name}:{TAGGER_JOB} runs no actions/checkout, so this assertion "
        "cannot mean anything."
    )
    for step in checkouts:
        with_block = step.get("with") or {}
        assert with_block.get("persist-credentials") is False, (
            f"{TAGGER.name}:{TAGGER_JOB} checks out without "
            "`persist-credentials: false`. The persisted workflow-token extraheader "
            "overrides the App credential in the push URL, the tag is pushed as "
            "github-actions[bot], no push event is delivered, and release.yml never "
            "starts."
        )


def test_tagger_mints_the_app_token_fail_closed() -> None:
    """Condition 2: an unmintable token stops the push rather than degrading it."""
    text = _step_text()

    assert "actions/create-github-app-token" in text, (
        f"{TAGGER.name}:{TAGGER_JOB} pushes a release tag but never mints an App "
        "installation token."
    )
    assert re.search(r"secrets\.ONEXBOT_OCC_APP_ID\b", text) is not None, (
        f"{TAGGER.name}:{TAGGER_JOB} does not mint from ONEXBOT_OCC_APP_ID."
    )
    assert re.search(r"secrets\.ONEXBOT_OCC_PRIVATE_KEY\b", text) is not None, (
        f"{TAGGER.name}:{TAGGER_JOB} does not mint from ONEXBOT_OCC_PRIVATE_KEY."
    )

    fallback = re.search(
        r"steps\.[\w-]+\.outputs\.token\s*\|\|\s*secrets\.GITHUB_TOKEN", text
    )
    assert fallback is None, (
        f"{TAGGER.name}:{TAGGER_JOB} falls back to secrets.GITHUB_TOKEN when the "
        "mint fails. That silently restores the suppressed push while the job still "
        "reports success -- the exact confound that produced the wrong org-wide "
        "finding in August."
    )
    # Broader than the fallback expression: the default token must not be reachable
    # from this job in any form. Comments are dropped by the YAML load, so prose
    # explaining the prohibition cannot trip this.
    assert "secrets.GITHUB_TOKEN" not in text, (
        f"{TAGGER.name}:{TAGGER_JOB} references secrets.GITHUB_TOKEN. The tag push "
        "must have no route back to the workflow token."
    )
    assert "github.token" not in text, (
        f"{TAGGER.name}:{TAGGER_JOB} references github.token -- the same failure, "
        "spelled the other way."
    )


def test_tagger_tags_as_the_app_identity() -> None:
    """An annotated tag carries a tagger identity, so it is attributable or it is not.

    A fabricated address resolves to no GitHub account and renders unlinked, proving
    nothing (OMN-18273 AC-4). The numeric prefix is what links the address to the bot
    account.
    """
    text = _step_text()
    assert APP_BOT_NAME in text, (
        f"{TAGGER.name}:{TAGGER_JOB} does not set user.name to {APP_BOT_NAME!r}."
    )
    assert APP_BOT_EMAIL in text, (
        f"{TAGGER.name}:{TAGGER_JOB} does not set user.email to {APP_BOT_EMAIL!r}."
    )
    for forbidden in ("bot@omninode.ai", "41898282+github-actions[bot]"):
        assignment = re.search(
            r"git config (?:--global )?user\.(?:name|email) [\"']?"
            + re.escape(forbidden),
            text,
        )
        assert assignment is None, (
            f"{TAGGER.name}:{TAGGER_JOB} still assigns the {forbidden!r} identity."
        )
