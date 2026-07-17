# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the node_pattern_extraction_compute ``__main__`` CLI.

Covers the argparse entry point in
``omniintelligence.nodes.node_pattern_extraction_compute.__main__``:

* documented exit codes — 0 (success), 1 (input error), 2 (extraction error)
* happy-path extraction over minimal valid input (json / summary / file output)
* CLI-override plumbing (thresholds + extractor disable flags)

The CLI is driven in-process by patching ``sys.argv`` and invoking ``main()``,
so coverage is attributed to the module under test. ``main()`` raises
``SystemExit`` on error paths (via ``sys.exit``) and returns ``None`` on success.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute import __main__ as cli

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def _valid_input_dict() -> dict[str, Any]:
    """A minimal but schema-valid pattern-extraction input document.

    One session snapshot is sufficient to satisfy the ``min_length=1``
    constraint on ``session_snapshots`` and to run the extraction pipeline
    to completion (zero patterns found is still a success).
    """
    started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat()
    ended = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC).isoformat()
    return {
        "session_snapshots": [
            {
                "session_id": "session-cli-001",
                "working_directory": "/project",
                "started_at": started,
                "ended_at": ended,
                "files_accessed": ["src/api/routes.py", "src/handlers/api_handler.py"],
                "files_modified": ["src/api/routes.py"],
                "tools_used": ["Read", "Edit"],
                "errors_encountered": [],
                "outcome": "success",
            }
        ]
    }


def _write_input(tmp_path: Path, data: dict[str, Any]) -> str:
    """Write ``data`` as JSON to a temp file and return its path string."""
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    return str(input_path)


def _run_cli(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    """Invoke ``cli.main()`` with a patched ``sys.argv``.

    ``argv`` is the argument list *after* the program name.
    """
    monkeypatch.setattr("sys.argv", ["prog", *argv])
    cli.main()


# =============================================================================
# Happy path (exit 0)
# =============================================================================


def test_happy_path_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Valid input + default (json) format emits parseable JSON and exits 0."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    _run_cli(monkeypatch, [input_file])

    out = capsys.readouterr().out
    payload = json.loads(out)
    # The full ModelPatternExtractionOutput is serialized; success is truthy.
    assert payload["success"] is True


def test_happy_path_summary_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--output-format summary`` emits the human-readable text summary."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    _run_cli(monkeypatch, [input_file, "--output-format", "summary"])

    out = capsys.readouterr().out
    assert "Pattern Extraction Result" in out
    assert "Metrics" in out


def test_happy_path_output_to_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--output FILE`` writes JSON results to the file instead of stdout."""
    input_file = _write_input(tmp_path, _valid_input_dict())
    output_file = tmp_path / "results.json"

    _run_cli(
        monkeypatch,
        [input_file, "--output-format", "json", "--output", str(output_file)],
    )

    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["success"] is True


def test_happy_path_reads_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Passing ``-`` reads the input document from stdin."""
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_valid_input_dict())))

    _run_cli(monkeypatch, ["-"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True


def test_extractor_disable_flags_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Extractor disable flags + threshold overrides run without error (exit 0)."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    _run_cli(
        monkeypatch,
        [
            input_file,
            "--no-file-patterns",
            "--no-error-patterns",
            "--no-architecture",
            "--no-tool-patterns",
            "--no-tool-failures",
            "--min-confidence",
            "0.75",
            "--min-occurrences",
            "3",
            "--max-insights-per-type",
            "10",
        ],
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True


# =============================================================================
# Input errors (exit 1)
# =============================================================================


def test_exit_1_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nonexistent input path exits 1 with an error message on stderr."""
    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, ["/nonexistent/path/does_not_exist.json"])
    assert exc.value.code == 1


def test_exit_1_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Malformed JSON in the input file exits 1."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [str(bad)])
    assert exc.value.code == 1


def test_exit_1_non_object_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Top-level JSON that is not an object (dict) exits 1."""
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [str(arr)])
    assert exc.value.code == 1


def test_exit_1_missing_session_snapshots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Input JSON without the required ``session_snapshots`` key exits 1."""
    input_file = _write_input(tmp_path, {"options": {}})

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file])
    assert exc.value.code == 1


def test_exit_1_min_confidence_out_of_range(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--min-confidence`` outside [0.0, 1.0] exits 1."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file, "--min-confidence", "1.5"])
    assert exc.value.code == 1


def test_exit_1_min_occurrences_below_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--min-occurrences`` below 1 exits 1."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file, "--min-occurrences", "0"])
    assert exc.value.code == 1


def test_exit_1_max_insights_below_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--max-insights-per-type`` below 1 exits 1."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file, "--max-insights-per-type", "0"])
    assert exc.value.code == 1


def test_exit_1_invalid_session_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A session snapshot missing required fields fails validation and exits 1."""
    input_file = _write_input(
        tmp_path,
        {"session_snapshots": [{"working_directory": "/project"}]},
    )

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file])
    assert exc.value.code == 1


# =============================================================================
# Extraction error (exit 2)
# =============================================================================


def test_exit_2_extraction_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unrecoverable failure during extraction exits 2."""
    input_file = _write_input(tmp_path, _valid_input_dict())

    def _boom(_input: Any) -> Any:
        raise RuntimeError("simulated extraction failure")

    # Patch the symbol as imported into the __main__ module.
    monkeypatch.setattr(cli, "extract_all_patterns", _boom)

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [input_file])
    assert exc.value.code == 2


# =============================================================================
# Parser construction / --help
# =============================================================================


def test_help_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--help`` prints usage and exits 0 (argparse convention)."""
    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, ["--help"])
    assert exc.value.code == 0


def test_build_parser_defaults() -> None:
    """The parser exposes the documented defaults for key options."""
    parser = cli._build_parser()
    args = parser.parse_args(["input.json"])
    assert args.output_format == "json"
    assert args.indent == 2
    assert args.min_confidence is None
    assert args.no_architecture is False
