# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-20074: ci.yml's ``contract-validation`` job points at the validator that runs.

``contract-validation.yml`` validates the branch ticket's contract with omnibase_core's
``ModelTicketContract`` (see ``test_contract_validation_core_validator_omn20074.py``).
The job of the same name in ci.yml is a notice-only shim; its notice still named the
central onex_change_control validator, which this repository no longer calls. The
assertions read the parsed job, so the other onex_change_control mentions in ci.yml
(the boundary-parity lane) are out of scope here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
JOB_KEY = "contract-validation"
JOB_NAME = "Contract Validation"
VALIDATING_WORKFLOW = ".github/workflows/contract-validation.yml"


def _job() -> dict[str, Any]:
    data = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"][JOB_KEY]
    assert isinstance(job, dict)
    return job


def test_job_names_are_unchanged() -> None:
    assert _job()["name"] == JOB_NAME


def test_job_names_no_onex_change_control() -> None:
    dumped = yaml.safe_dump(_job())
    assert "onex_change_control" not in dumped
    assert "onex-change-control" not in dumped


def test_job_notice_names_the_validator_that_runs() -> None:
    dumped = yaml.safe_dump(_job())
    assert VALIDATING_WORKFLOW in dumped
    assert "ModelTicketContract" in dumped
    assert (REPO_ROOT / VALIDATING_WORKFLOW).is_file()
