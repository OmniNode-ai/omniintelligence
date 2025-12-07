# SPDX-License-Identifier: Apache-2.0
"""
I/O Audit CLI for ONEX Node Purity Enforcement.

Detects forbidden I/O patterns in ONEX compute nodes through AST-based static
analysis. Enforces the "pure compute / no I/O" architectural invariant.

Usage:
    python -m omniintelligence.audit
    python -m omniintelligence.audit src/omniintelligence/nodes
    python -m omniintelligence.audit --whitelist tests/audit/io_audit_whitelist.yaml
    python -m omniintelligence.audit --verbose
    python -m omniintelligence.audit --json

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

from omniintelligence.audit.io_audit import (
    IO_AUDIT_TARGETS,
    REMEDIATION_HINTS,
    EnumIOAuditRule,
    ModelAuditResult,
    ModelIOAuditViolation,
    run_audit,
)

# JSON output indentation (spaces)
JSON_INDENT_SPACES = 2


def _format_violation_line(violation: ModelIOAuditViolation) -> str:
    """Format a single violation for display within a file group.

    Args:
        violation: The violation to format.

    Returns:
        Formatted string in format: "Line N: [rule] message"
        (File path is omitted since it's shown in the group header)
    """
    return f"Line {violation.line}: [{violation.rule.value}] {violation.message}"


def _format_text_output(result: ModelAuditResult, verbose: bool = False) -> str:
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

    return "\n".join(lines)


def _format_json_output(result: ModelAuditResult) -> str:
    """Format audit result as JSON for CI/CD integration.

    Args:
        result: The audit result to format.

    Returns:
        JSON string with structure:
        {
            "violations": [...],
            "files_scanned": N,
            "is_clean": bool
        }
    """
    return json.dumps(
        {
            "violations": [
                {
                    "file": str(v.file),
                    "line": v.line,
                    "column": v.column,
                    "rule": v.rule.value,
                    "message": v.message,
                }
                for v in result.violations
            ],
            "files_scanned": result.files_scanned,
            "is_clean": result.is_clean,
        },
        indent=JSON_INDENT_SPACES,
    )


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
  %(prog)s                                   # Audit default targets
  %(prog)s src/myproject/nodes              # Audit specific directory
  %(prog)s -w tests/audit/whitelist.yaml    # Use custom whitelist
  %(prog)s --json                            # JSON output for CI
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
        default=None,
        metavar="PATH",
        help="Path to whitelist YAML file",
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

    parsed_args = parser.parse_args(args)

    try:
        # Determine targets
        targets = parsed_args.targets if parsed_args.targets else None

        # Run the audit
        result = run_audit(
            targets=targets,
            whitelist_path=parsed_args.whitelist,
        )

        # Format and print output
        if parsed_args.json:
            output = _format_json_output(result)
        else:
            output = _format_text_output(result, verbose=parsed_args.verbose)

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
                    {"error": str(e), "error_type": "file_not_found"},
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
                    {"error": str(e), "error_type": "unexpected_error"},
                    indent=JSON_INDENT_SPACES,
                )
            )
        else:
            print(error_msg, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
