# SPDX-License-Identifier: Apache-2.0
"""
I/O Audit CLI for ONEX Node Purity Enforcement.

Detects forbidden I/O patterns in ONEX compute nodes through AST-based static
analysis. Enforces the "pure compute / no I/O" architectural invariant.

The default whitelist path (tests/audit/io_audit_whitelist.yaml) is used
automatically unless overridden with --whitelist. This ensures consistent
behavior across CI, pre-commit hooks, and local runs.

Usage:
    python -m omniintelligence.audit
    python -m omniintelligence.audit src/omniintelligence/nodes
    python -m omniintelligence.audit --whitelist custom_whitelist.yaml
    python -m omniintelligence.audit --verbose
    python -m omniintelligence.audit --json
    python -m omniintelligence.audit --dry-run
    python -m omniintelligence.audit --metrics

Forbidden Patterns:
    - net-client: Network/DB client imports (confluent_kafka, httpx, asyncpg, etc.)
    - env-access: Environment variable access (os.environ, os.getenv)
    - file-io: File system operations (open(), Path.read_text(), FileHandler)

Exit Codes:
    0 - Success: No I/O violations found
    1 - Violations found: One or more files contain forbidden I/O patterns
    2 - Error: CLI usage error or unexpected failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from omniintelligence.audit.io_audit import (
    DEFAULT_WHITELIST_PATH,
    IO_AUDIT_TARGETS,
    REMEDIATION_HINTS,
    EnumIOAuditRule,
    ModelAuditMetrics,
    ModelAuditResult,
    ModelIOAuditViolation,
    ModelWhitelistConfig,
    discover_python_files,
    load_whitelist,
    run_audit,
)

# JSON output indentation (spaces)
JSON_INDENT_SPACES = 2


def _format_dry_run_output(
    files: list[Path],
    whitelist: ModelWhitelistConfig,
    targets: list[str],
) -> str:
    """Format dry-run output showing what would be scanned.

    Args:
        files: List of files that would be scanned.
        whitelist: Loaded whitelist configuration.
        targets: Target directories being scanned.

    Returns:
        Formatted dry-run output string.
    """
    lines: list[str] = []
    lines.append("DRY RUN - No audit performed")
    lines.append("")

    # Show target directories
    lines.append(f"Target directories: {', '.join(targets)}")
    lines.append("")

    # Show files that would be scanned
    lines.append(f"Files that would be scanned ({len(files)} files):")
    if files:
        for file_path in files:
            lines.append(f"  - {file_path}")
    else:
        lines.append("  (no Python files found)")
    lines.append("")

    # Show whitelist entries
    if whitelist.files:
        lines.append(f"Whitelist entries loaded ({len(whitelist.files)} entries):")
        for entry in whitelist.files:
            rules_str = ", ".join(entry.allowed_rules) if entry.allowed_rules else "all"
            lines.append(f"  - {entry.path} [{rules_str}]")
    else:
        lines.append("Whitelist entries loaded (0 entries)")

    return "\n".join(lines)


def _format_dry_run_json(
    files: list[Path],
    whitelist: ModelWhitelistConfig,
    targets: list[str],
) -> str:
    """Format dry-run output as JSON.

    Args:
        files: List of files that would be scanned.
        whitelist: Loaded whitelist configuration.
        targets: Target directories being scanned.

    Returns:
        JSON string with dry-run information.
    """
    return json.dumps(
        {
            "dry_run": True,
            "targets": targets,
            "files": [str(f) for f in files],
            "files_count": len(files),
            "whitelist_entries": [
                {
                    "path": entry.path,
                    "allowed_rules": entry.allowed_rules,
                    "reason": entry.reason,
                }
                for entry in whitelist.files
            ],
            "whitelist_entries_count": len(whitelist.files),
        },
        indent=JSON_INDENT_SPACES,
    )


def _format_violation_line(violation: ModelIOAuditViolation) -> str:
    """Format a single violation for display within a file group.

    Args:
        violation: The violation to format.

    Returns:
        Formatted string in format: "Line N: [rule] message"
        (File path is omitted since it's shown in the group header)
    """
    return f"Line {violation.line}: [{violation.rule.value}] {violation.message}"


def _format_metrics_text(metrics: ModelAuditMetrics, files_scanned: int) -> str:
    """Format metrics as human-readable text.

    Args:
        metrics: The audit metrics to format.
        files_scanned: Number of files scanned.

    Returns:
        Formatted metrics text block.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("Metrics:")
    lines.append(f"  Files scanned: {files_scanned}")

    # Format duration - show seconds for readability
    duration_sec = metrics.duration_ms / 1000.0
    lines.append(f"  Duration: {duration_sec:.2f}s")

    lines.append(f"  Violations found: {metrics.violations_total}")
    lines.append(f"  Whitelisted (YAML): {metrics.whitelisted_yaml_count}")
    lines.append(f"  Whitelisted (pragma): {metrics.whitelisted_pragma_count}")

    # Calculate final violations
    final_violations = (
        metrics.violations_total
        - metrics.whitelisted_yaml_count
        - metrics.whitelisted_pragma_count
    )
    lines.append(f"  Final violations: {final_violations}")

    # Add violations by rule breakdown if any violations found
    if metrics.violations_by_rule:
        lines.append("  By rule:")
        for rule_id in sorted(metrics.violations_by_rule.keys()):
            count = metrics.violations_by_rule[rule_id]
            lines.append(f"    {rule_id}: {count}")

    return "\n".join(lines)


def _format_text_output(
    result: ModelAuditResult,
    verbose: bool = False,
    show_metrics: bool = False,
) -> str:
    """Format audit result as human-readable text.

    Output format groups violations by file to reduce redundancy:
        src/path/file.py:
          Line 5: [net-client] Forbidden import: confluent_kafka
          Line 12: [env-access] Forbidden call: os.getenv()
          -> Hints: Move to Effect node...; Pass config via constructor...

        Summary: 2 violations in 1 file (5 files scanned)

    Args:
        result: The audit result to format.
        verbose: If True, include whitelist usage hints.
        show_metrics: If True, include detailed metrics section.

    Returns:
        Formatted text output.
    """
    lines: list[str] = []

    if result.is_clean:
        lines.append(f"No I/O violations found. ({result.files_scanned} files scanned)")
    else:
        # Group violations by file for better readability
        violations_by_file: dict[Path, list[ModelIOAuditViolation]] = {}
        for v in result.violations:
            if v.file not in violations_by_file:
                violations_by_file[v.file] = []
            violations_by_file[v.file].append(v)

        for file_path, file_violations in sorted(violations_by_file.items()):
            lines.append(f"{file_path}:")

            # Collect unique rules for hint deduplication
            rules_in_file: set[EnumIOAuditRule] = set()

            for v in sorted(file_violations, key=lambda x: x.line):
                lines.append(f"  {_format_violation_line(v)}")
                rules_in_file.add(v.rule)

            # Add deduplicated hints for this file
            hints = [
                REMEDIATION_HINTS[rule]
                for rule in sorted(rules_in_file, key=lambda r: r.value)
                if rule in REMEDIATION_HINTS
            ]
            if hints:
                lines.append(f"  -> Hints: {'; '.join(hints)}")

        # Compact summary
        file_count = len(violations_by_file)
        lines.append("")
        lines.append(
            f"Summary: {len(result.violations)} violation(s) in {file_count} file(s) "
            f"({result.files_scanned} files scanned)"
        )

    if verbose and not result.is_clean:
        lines.append("")
        lines.append("Use --whitelist to specify allowed exceptions.")
        lines.append("See CLAUDE.md for whitelist hierarchy documentation.")

    # Add metrics section if requested and available
    if show_metrics and result.metrics is not None:
        lines.append(_format_metrics_text(result.metrics, result.files_scanned))

    return "\n".join(lines)


def _format_json_output(result: ModelAuditResult, show_metrics: bool = False) -> str:
    """Format audit result as JSON for CI/CD integration.

    Args:
        result: The audit result to format.
        show_metrics: If True, include detailed metrics in output.

    Returns:
        JSON string with structure:
        {
            "violations": [...],
            "files_scanned": N,
            "is_clean": bool,
            "metrics": {...}  // Only if show_metrics is True
        }
    """
    output: dict[str, Any] = {
        "violations": [
            {
                "file": str(v.file),
                "line": v.line,
                "column": v.column,
                "rule": v.rule.value,
                "message": v.message,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ],
        "files_scanned": result.files_scanned,
        "is_clean": result.is_clean,
    }

    # Add metrics if requested and available
    if show_metrics and result.metrics is not None:
        output["metrics"] = {
            "duration_ms": result.metrics.duration_ms,
            "violations_by_rule": result.metrics.violations_by_rule,
            "whitelisted_yaml": result.metrics.whitelisted_yaml_count,
            "whitelisted_pragma": result.metrics.whitelisted_pragma_count,
        }

    return json.dumps(output, indent=JSON_INDENT_SPACES)


def main(args: list[str] | None = None) -> int:
    """CLI entry point for I/O audit.

    Args:
        args: Command line arguments (uses sys.argv if None).

    Returns:
        Exit code following Unix conventions:
            0 - Success: No I/O violations found
            1 - Violations found: One or more files contain forbidden I/O patterns
            2 - Error: CLI usage error or unexpected failure
    """
    parser = argparse.ArgumentParser(
        description="ONEX node I/O audit - detect forbidden I/O patterns in compute nodes",
        prog="python -m omniintelligence.audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Forbidden patterns:
  net-client   Network/DB client imports (confluent_kafka, httpx, asyncpg, etc.)
  env-access   Environment variable access (os.environ, os.getenv)
  file-io      File system operations (open(), Path.read_text(), FileHandler)

Examples:
  %(prog)s                                   # Audit with default whitelist
  %(prog)s src/myproject/nodes              # Audit specific directory
  %(prog)s -w custom_whitelist.yaml         # Use custom whitelist
  %(prog)s --json                            # JSON output for CI
  %(prog)s --dry-run                         # Show what would be scanned
  %(prog)s --metrics                         # Include timing and whitelist stats
  %(prog)s --json --metrics                  # JSON output with metrics
""",
    )

    parser.add_argument(
        "targets",
        nargs="*",
        default=None,
        help=f"Directories to scan (default: {', '.join(IO_AUDIT_TARGETS)})",
    )

    parser.add_argument(
        "--whitelist",
        "-w",
        type=Path,
        default=Path(DEFAULT_WHITELIST_PATH),
        metavar="PATH",
        help=f"Path to whitelist YAML file (default: {DEFAULT_WHITELIST_PATH})",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with additional context",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format for CI integration",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what files would be scanned without running the audit",
    )

    parser.add_argument(
        "--metrics",
        "-m",
        action="store_true",
        help="Include detailed metrics (timing, whitelist stats, violations by rule)",
    )

    parsed_args = parser.parse_args(args)

    try:
        # Determine targets
        targets = parsed_args.targets if parsed_args.targets else IO_AUDIT_TARGETS

        # Handle dry-run mode
        if parsed_args.dry_run:
            # Discover files that would be scanned
            files = discover_python_files(targets)

            # Load whitelist (uses default path if not overridden)
            whitelist = load_whitelist(parsed_args.whitelist)

            # Format and print dry-run output
            if parsed_args.json:
                output = _format_dry_run_json(files, whitelist, list(targets))
            else:
                output = _format_dry_run_output(files, whitelist, list(targets))

            print(output)
            return 0

        # Run the audit
        result = run_audit(
            targets=targets,
            whitelist_path=parsed_args.whitelist,
            collect_metrics=parsed_args.metrics,
        )

        # Format and print output
        if parsed_args.json:
            output = _format_json_output(result, show_metrics=parsed_args.metrics)
        else:
            output = _format_text_output(
                result,
                verbose=parsed_args.verbose,
                show_metrics=parsed_args.metrics,
            )

        print(output)

        # Determine exit code
        if result.is_clean:
            return 0
        else:
            return 1

    except FileNotFoundError as e:
        error_msg = f"Error: {e}"
        if parsed_args.json:
            print(
                json.dumps(
                    {"error": error_msg, "error_type": "file_not_found"},
                    indent=JSON_INDENT_SPACES,
                )
            )
        else:
            print(error_msg, file=sys.stderr)
        return 2

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if parsed_args.json:
            print(
                json.dumps(
                    {"error": error_msg, "error_type": "unexpected_error"},
                    indent=JSON_INDENT_SPACES,
                )
            )
        else:
            print(error_msg, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
