# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Regression tests for scripts/validate.py::run_contract_linter() (OMN-16580).

Wave-3 audit found that ``run_contract_linter()`` builds its subprocess
command against the nonexistent module ``omniintelligence.tools.contract_linter``
(``src/omniintelligence/tools/`` does not exist) instead of the real
``omniintelligence.validators.contract_linter``. The default (non-verbose)
invocation also swallows the resulting ``ModuleNotFoundError`` — it captures
stderr and discards it, downgrading the failure to a generic
"Contract validation failed (exit code: N)" message with no indication of
the real cause.

Note: these tests deliberately do NOT assert that ``run_contract_linter()``
*passes* against this repo's live contract.yaml files. A separate,
pre-existing defect (contract-linter's own schema requires a
``contract_version`` field that 66/67 live node contracts don't have — see
the follow-up ticket filed alongside OMN-16580) means most of them
currently fail real schema validation for reasons entirely unrelated to
the module-path bug. Coupling this regression test to that would make it
flaky/wrong for the wrong reason. Instead these tests isolate exactly the
two behaviors OMN-16580 is about: which module gets invoked, and whether a
failing subprocess's stderr is surfaced.

Both tests fail against the pre-fix code:

* ``test_run_contract_linter_invokes_a_resolvable_module`` — captures the
  actual ``python -m <module>`` command ``run_contract_linter()`` builds and
  asserts that module resolves via ``importlib.util.find_spec``. Pre-fix,
  the invoked module (``omniintelligence.tools.contract_linter``) does not
  exist, so it fails to resolve.
* ``test_run_contract_linter_surfaces_subprocess_stderr_on_failure`` —
  simulates a subprocess failure with distinctive stderr output and asserts
  it is surfaced in ``ValidationResult.message``. Pre-fix, captured stderr
  is discarded entirely and never reaches the message.
"""

from __future__ import annotations

import importlib.util
import subprocess
from dataclasses import dataclass, field

import pytest

from scripts.validate import run_contract_linter


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    args: list[str] = field(default_factory=list)


@pytest.mark.unit
class TestContractLinterModulePath:
    def test_run_contract_linter_invokes_a_resolvable_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ``python -m <module>`` command must name a module that exists.

        Captures the real ``cmd`` list ``run_contract_linter()`` builds
        (without letting the subprocess actually execute) and resolves the
        module name it names via ``importlib.util.find_spec`` — the same
        mechanism ``python -m`` itself uses. This pins the exact defect: an
        invocation naming a module that cannot be found.
        """
        captured: dict[str, list[str]] = {}

        def _fake_run(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
            captured["cmd"] = cmd
            return _FakeCompletedProcess(returncode=0, args=cmd)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        run_contract_linter(verbose=False)

        assert "cmd" in captured, (
            "expected run_contract_linter() to call subprocess.run"
        )
        cmd = captured["cmd"]
        assert "-m" in cmd, f"expected a `python -m <module>` invocation, got: {cmd}"
        module_name = cmd[cmd.index("-m") + 1]

        try:
            spec = importlib.util.find_spec(module_name)
        except ModuleNotFoundError:
            spec = None

        assert spec is not None, (
            f"run_contract_linter() invokes `python -m {module_name}`, but that "
            f"module does not exist/resolve in this environment"
        )

    def test_run_contract_linter_surfaces_subprocess_stderr_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing subprocess's stderr must reach ValidationResult.message.

        Regardless of *why* the subprocess fails (wrong module, a genuine
        contract violation, etc.), discarding captured stderr and reporting
        only a bare exit code hides the real cause. This simulates a failure
        directly (independent of the module-path bug) to pin the propagation
        behavior itself.
        """
        marker = "ModuleNotFoundError: No module named 'omniintelligence.tools'"

        def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompletedProcess:
            return _FakeCompletedProcess(returncode=1, stderr=marker.encode())

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = run_contract_linter(verbose=False)

        assert not result.passed
        assert marker in result.message, (
            f"expected the real subprocess error to be surfaced in the "
            f"validation message, got: {result.message!r}"
        )
