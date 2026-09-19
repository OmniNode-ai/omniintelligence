# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""`sibling-lock-refresh.yml` must name its ticket where the gate reads it.

OMN-18753. The Receipt Gate resolves ``Evidence-Ticket`` from the PR title and
then requires that same ticket to appear in the BRANCH NAME or in one of the
PR's COMMIT MESSAGES. The title alone does not satisfy it.

This workflow named OMN-13902 in the title only, so every PR it opened failed
identity binding with ``neither the branch name nor any commit message
references OMN-13902`` and could not merge until somebody hand-pushed a binding
commit. Measured on this repository: #907, #914 and #919 each needed one
(``chore(OMN-13902): bind sibling lock refresh``), which is an automation that
cannot land its own output.

That is worse than an ordinary red check. This workflow is the sanctioned path
for advancing the sibling pins, so an automation whose every PR needs a human
push is one people route around -- and routing around it means hand-editing the
rev, the exact act that desynchronises the lock from the canonical clone.

The properties are asserted over the workflow TEXT rather than over a diff, so
an edit that drops either surface fails here instead of passing review and
being discovered by the next bot PR. omniclaude fixed the same template defect
under this ticket; this is the propagation to this repository's copy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "sibling-lock-refresh.yml"
)

TICKET = "OMN-13902"


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), f"{WORKFLOW} is missing"
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.unit
def test_bot_branch_name_carries_the_ticket() -> None:
    """The branch name is the first surface the identity binding accepts."""
    lines = [
        line
        for line in _workflow_text().splitlines()
        if line.strip().startswith("BRANCH=")
    ]
    assert lines, "the workflow no longer assigns BRANCH"
    for line in lines:
        assert TICKET.lower() in line.lower(), (
            f"the bot branch name carries no ticket ({line.strip()!r}); the "
            f"Receipt Gate's identity binding reads the branch name, and the "
            f"PR title alone does not satisfy it"
        )


@pytest.mark.unit
def test_bot_commit_message_carries_the_ticket() -> None:
    """The commit message is the other surface, and the fallback when a
    ticket is filed after the branch already exists."""
    lines = [
        line
        for line in _workflow_text().splitlines()
        if line.strip().startswith("git commit -m")
    ]
    assert lines, "the workflow no longer commits"
    for line in lines:
        assert TICKET in line, (
            f"the bot commit message carries no ticket ({line.strip()!r}); it "
            f"is the other surface the identity binding accepts"
        )


@pytest.mark.unit
def test_pr_title_still_carries_the_ticket() -> None:
    """The title is what Evidence-Ticket resolves FROM; binding a branch and a
    commit to a ticket the title no longer names would bind them to nothing."""
    text = _workflow_text()
    title_lines = [
        line for line in text.splitlines() if line.strip().startswith("--title ")
    ]
    assert title_lines, "the workflow no longer passes a PR title"
    assert any(TICKET in line for line in title_lines), (
        f"no --title line names {TICKET}; the Receipt Gate reads Evidence-Ticket "
        f"from the title, so the branch and commit bindings would have nothing "
        f"to agree with"
    )
