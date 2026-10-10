# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-20074: omnibase_core's no-untracked-todos hook decides what onex_change_control's did.

OCC retirement S8: the hook of this id moved from the change-control repository to
omnibase_core. Each case below was run through onex_change_control's check-todo-format
at rev 8d7e85bc00e7f1b1306d1cb40949be1ab6e7e91a (the rev this repository pinned), and
its printed output and exit code are recorded verbatim; omnibase_core's handler must
reproduce them. The one deliberate difference is the handler's own basename
(handler_todo_format.py), which the port also skips; it is not replayed.

The unfinished-work markers are spelled @T@/@F@/@H@ in the recorded text and filled in
at run time, so this file carries no bare marker itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from omnibase_core.handlers.handler_todo_format import main

pytestmark = pytest.mark.unit

FILL = {"@T@": "TO" + "DO", "@F@": "FIX" + "ME", "@H@": "HA" + "CK"}

# (case name, files to create, argv, recorded stdout, recorded exit code)
CASES: list[tuple[str, dict[str, str], list[str], str, int]] = [
    (
        "bare_markers_flagged",
        {"a.py": "value = 1\n# @T@: later\n# @F@ x\n# @H@\n"},
        ["a.py"],
        "a.py:2: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:3: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:4: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n3 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "valid_marker_does_not_hide_bare_marker",
        {"a.py": "# @T@(OMN-123): ok\n# @T@(OMN-123): ok; @F@ bare\n"},
        ["a.py"],
        "a.py:2: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "ticket_format_variants",
        {
            "a.py": "# @T@ (OMN-123): spaced\n"
            "# @T@(OMN-123) nocolon\n"
            "# @T@(OMN-XXXX): placeholder\n"
            "# @T@(ABC-123): wrong\n"
            "# @T@(OMN-7): fine\n"
        },
        ["a.py"],
        "a.py:1: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:2: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:3: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:4: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n4 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "exemption_needs_a_reason",
        {
            "a.py": "# @T@: x  # @T@_FORMAT_EXEMPT: legacy reason\n"
            "# @T@: y  # @T@_FORMAT_EXEMPT:   \n"
        },
        ["a.py"],
        "a.py:2: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "markers_inside_string_literals",
        {"a.py": "s = '# @T@: in string'\nt = \"@F@ in string\"\nu = 'a'  # @H@\n"},
        ["a.py"],
        "a.py:3: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "exemption_token_inside_a_string",
        {"a.py": "s = '# @T@_FORMAT_EXEMPT: reason'  # @T@: x\n"},
        ["a.py"],
        "a.py:1: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "triple_quoted_docstring",
        {"a.py": '"""\n# @T@: in docstring\n"""\n# @T@: after docstring\n'},
        ["a.py"],
        "a.py:4: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "single_line_docstring",
        {"a.py": '"""# @T@ x"""\n# @F@ y\n'},
        ["a.py"],
        "a.py:2: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "block_comment_lines",
        {"a.py": "/*\n# @T@: inside block\n*/\n# @H@: after\n"},
        ["a.py"],
        "a.py:4: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "excluded_path_segments",
        {
            "tests/a.py": "# @T@: x\n",
            "docs/a.py": "# @T@: x\n",
            "examples/a.py": "# @T@: x\n",
            "fixtures/a.py": "# @T@: x\n",
            "vendored/a.py": "# @T@: x\n",
        },
        ["tests/a.py", "docs/a.py", "examples/a.py", "fixtures/a.py", "vendored/a.py"],
        "",
        0,
    ),
    (
        "similar_path_segment_is_scanned",
        {"tests_extra/a.py": "# @T@: x\n"},
        ["tests_extra/a.py"],
        "tests_extra/a.py:1: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n1 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "source_basename_is_skipped",
        {"check_todo_format.py": "# @T@: x\n"},
        ["check_todo_format.py"],
        "",
        0,
    ),
    (
        "non_python_file_is_skipped",
        {"notes.txt": "# @T@: x\n", "b.md": "# @F@ y\n"},
        ["notes.txt", "b.md"],
        "",
        0,
    ),
    (
        "missing_file_is_skipped",
        {},
        ["absent.py"],
        "",
        0,
    ),
    (
        "clean_and_empty_files",
        {"a.py": "x = 1\n", "b.py": ""},
        ["a.py", "b.py"],
        "",
        0,
    ),
    (
        "several_files_keep_argument_order",
        {"b.py": "# @H@\n", "a.py": "# @T@: x\n"},
        ["b.py", "a.py"],
        "b.py:1: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\na.py:1: bare @T@/@F@/@H@ without ticket reference -- use format: # @T@(OMN-XXXX): description\n\n2 violation(s). Use format: # @T@(OMN-XXXX): description\n",
        1,
    ),
    (
        "no_arguments",
        {},
        [],
        "",
        0,
    ),
]


def _fill(text: str) -> str:
    for token, marker in FILL.items():
        text = text.replace(token, marker)
    return text


@pytest.mark.parametrize(
    ("name", "files", "argv", "recorded_stdout", "recorded_exit"),
    CASES,
    ids=[case[0] for case in CASES],
)
def test_core_handler_replays_the_recorded_change_control_decision(
    name: str,
    files: dict[str, str],
    argv: list[str],
    recorded_stdout: str,
    recorded_exit: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_fill(content), encoding="utf-8")
    assert main(argv) == recorded_exit
    captured = capsys.readouterr()
    assert captured.out == _fill(recorded_stdout)
    assert captured.err == ""


def test_a_flagged_case_is_among_the_replayed_cases() -> None:
    assert any(case[4] == 1 for case in CASES)
    assert any(case[4] == 0 for case in CASES)
