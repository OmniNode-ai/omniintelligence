"""CLI entry point for pattern_extraction_compute node.

Provides standalone execution of the pattern extraction compute node,
accepting session data as JSON input and writing results to stdout or a file.

Usage:
    python -m omniintelligence.nodes.node_pattern_extraction_compute --help
    python -m omniintelligence.nodes.node_pattern_extraction_compute input.json
    python -m omniintelligence.nodes.node_pattern_extraction_compute input.json \\
        --min-confidence 0.7 --output-format json
    python -m omniintelligence.nodes.node_pattern_extraction_compute input.json \\
        --no-architecture --no-tool-failures --output output.json

Input JSON Format:
    {
        "session_snapshots": [...],
        "options": {...},          # optional
        "existing_insights": [...] # optional
    }

Exit Codes:
    0 - Success: Extraction completed (even with zero patterns found)
    1 - Input error: Invalid JSON, missing required fields, file not found
    2 - Extraction error: Unrecoverable failure during extraction
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelExtractionConfig,
    ModelPatternExtractionInput,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m omniintelligence.nodes.node_pattern_extraction_compute",
        description=(
            "Extract codebase patterns from Claude Code session snapshots. "
            "Reads session data from a JSON file (or stdin if '-' is given) "
            "and writes extraction results to stdout or a file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction from file
  python -m omniintelligence.nodes.node_pattern_extraction_compute sessions.json

  # Read from stdin
  cat sessions.json | python -m omniintelligence.nodes.node_pattern_extraction_compute -

  # Tune thresholds
  python -m omniintelligence.nodes.node_pattern_extraction_compute sessions.json \\
      --min-confidence 0.75 --min-occurrences 3

  # Disable specific extractors
  python -m omniintelligence.nodes.node_pattern_extraction_compute sessions.json \\
      --no-architecture --no-tool-failures

  # Write JSON output to file
  python -m omniintelligence.nodes.node_pattern_extraction_compute sessions.json \\
      --output-format json --output results.json

  # Summary output (human-readable)
  python -m omniintelligence.nodes.node_pattern_extraction_compute sessions.json \\
      --output-format summary
""",
    )

    # Positional argument: input file
    parser.add_argument(
        "input",
        metavar="INPUT",
        help="Path to JSON file containing session data, or '-' to read from stdin.",
    )

    # Confidence / occurrence thresholds
    thresholds = parser.add_argument_group("extraction thresholds")
    thresholds.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        metavar="FLOAT",
        help=(
            "Minimum confidence threshold for patterns (0.0-1.0). "
            "Overrides the value in the input JSON options field. "
            "Default: 0.6"
        ),
    )
    thresholds.add_argument(
        "--min-occurrences",
        type=int,
        default=None,
        metavar="INT",
        help=(
            "Minimum number of occurrences for a pattern to be included. "
            "Overrides the value in the input JSON options field. "
            "Default: 2"
        ),
    )
    thresholds.add_argument(
        "--max-insights-per-type",
        type=int,
        default=None,
        metavar="INT",
        help=(
            "Maximum insights to return per insight type. "
            "Overrides the value in the input JSON options field. "
            "Default: 50"
        ),
    )

    # Extractor enable/disable flags
    extractors = parser.add_argument_group("extractor selection")
    extractors.add_argument(
        "--no-file-patterns",
        action="store_true",
        default=False,
        help="Disable file access pattern extraction.",
    )
    extractors.add_argument(
        "--no-error-patterns",
        action="store_true",
        default=False,
        help="Disable error pattern extraction.",
    )
    extractors.add_argument(
        "--no-architecture",
        action="store_true",
        default=False,
        help="Disable architecture pattern extraction.",
    )
    extractors.add_argument(
        "--no-tool-patterns",
        action="store_true",
        default=False,
        help="Disable tool usage pattern extraction.",
    )
    extractors.add_argument(
        "--no-tool-failures",
        action="store_true",
        default=False,
        help="Disable tool failure pattern extraction.",
    )

    # Output options
    output = parser.add_argument_group("output options")
    output.add_argument(
        "--output-format",
        choices=["json", "summary"],
        default="json",
        help=(
            "Output format. 'json' emits the full ModelPatternExtractionOutput "
            "as JSON. 'summary' emits a human-readable text summary. "
            "Default: json"
        ),
    )
    output.add_argument(
        "--output",
        metavar="FILE",
        default=None,
        help=(
            "Write output to FILE instead of stdout. "
            "Use with --output-format json to save results."
        ),
    )
    output.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="INT",
        help="JSON indentation level. Default: 2",
    )

    return parser


def _load_input(source: str) -> dict[str, Any]:
    """Load and parse JSON input from file path or stdin.

    Args:
        source: File path string or '-' for stdin.

    Returns:
        Parsed JSON as a dict.

    Raises:
        SystemExit(1): On file not found or invalid JSON.
    """
    try:
        if source == "-":
            raw = sys.stdin.read()
        else:
            path = Path(source)
            if not path.exists():
                print(f"Error: input file not found: {source}", file=sys.stderr)
                sys.exit(1)
            raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: failed to read input: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in input: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("Error: input JSON must be a JSON object (dict)", file=sys.stderr)
        sys.exit(1)

    return data


def _build_input(
    raw: dict[str, Any],
    args: argparse.Namespace,
) -> ModelPatternExtractionInput:
    """Construct ModelPatternExtractionInput from raw JSON and CLI overrides.

    CLI flag overrides take precedence over values in the input JSON
    ``options`` field. This allows per-run tuning without editing the
    input file.

    Args:
        raw: Parsed JSON dict from the input source.
        args: Parsed CLI arguments.

    Returns:
        Validated ModelPatternExtractionInput.

    Raises:
        SystemExit(1): On missing required fields or validation errors.
    """
    if "session_snapshots" not in raw:
        print(
            "Error: input JSON must contain 'session_snapshots' key",
            file=sys.stderr,
        )
        sys.exit(1)

    # Start with options from input JSON (if present), then apply CLI overrides
    options_dict: dict[str, Any] = dict(raw.get("options") or {})

    if args.min_confidence is not None:
        if not (0.0 <= args.min_confidence <= 1.0):
            print(
                f"Error: --min-confidence must be between 0.0 and 1.0, "
                f"got {args.min_confidence}",
                file=sys.stderr,
            )
            sys.exit(1)
        options_dict["min_confidence"] = args.min_confidence

    if args.min_occurrences is not None:
        if args.min_occurrences < 1:
            print(
                f"Error: --min-occurrences must be >= 1, got {args.min_occurrences}",
                file=sys.stderr,
            )
            sys.exit(1)
        options_dict["min_pattern_occurrences"] = args.min_occurrences

    if args.max_insights_per_type is not None:
        if args.max_insights_per_type < 1:
            print(
                f"Error: --max-insights-per-type must be >= 1, "
                f"got {args.max_insights_per_type}",
                file=sys.stderr,
            )
            sys.exit(1)
        options_dict["max_insights_per_type"] = args.max_insights_per_type

    # Apply extractor disable flags (CLI overrides JSON, but only to disable)
    if args.no_file_patterns:
        options_dict["extract_file_patterns"] = False
    if args.no_error_patterns:
        options_dict["extract_error_patterns"] = False
    if args.no_architecture:
        options_dict["extract_architecture_patterns"] = False
    if args.no_tool_patterns:
        options_dict["extract_tool_patterns"] = False
    if args.no_tool_failures:
        options_dict["extract_tool_failure_patterns"] = False

    try:
        config = ModelExtractionConfig(**options_dict)
    except Exception as exc:
        print(f"Error: invalid extraction options: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        input_data = ModelPatternExtractionInput(
            session_snapshots=raw["session_snapshots"],
            options=config,
            existing_insights=raw.get("existing_insights") or [],
        )
    except Exception as exc:
        print(f"Error: failed to parse input data: {exc}", file=sys.stderr)
        sys.exit(1)

    return input_data


def _format_summary(result: Any) -> str:
    """Format extraction result as human-readable summary.

    Args:
        result: ModelPatternExtractionOutput instance.

    Returns:
        Multi-line summary string.
    """
    lines = [
        "Pattern Extraction Result",
        "=" * 40,
        f"Status: {'success' if result.success else 'failed'}",
    ]

    if result.metadata:
        if result.metadata.status:
            lines.append(f"Completion status: {result.metadata.status}")
        if result.metadata.processing_time_ms is not None:
            lines.append(f"Processing time: {result.metadata.processing_time_ms:.1f}ms")
        if result.metadata.message:
            lines.append(f"Message: {result.metadata.message}")

    if result.metrics:
        lines.extend(
            [
                "",
                "Metrics",
                "-" * 20,
                f"  Sessions analyzed:      {result.metrics.sessions_analyzed}",
                f"  Total patterns found:   {result.metrics.total_patterns_found}",
                f"  New insights:           {result.metrics.new_insights_count}",
                f"  Updated insights:       {result.metrics.updated_insights_count}",
                f"  File patterns:          {result.metrics.file_patterns_count}",
                f"  Error patterns:         {result.metrics.error_patterns_count}",
                f"  Architecture patterns:  {result.metrics.architecture_patterns_count}",
                f"  Tool patterns:          {result.metrics.tool_patterns_count}",
                f"  Tool failure patterns:  {result.metrics.tool_failure_patterns_count}",
            ]
        )

    if result.new_insights:
        lines.extend(["", f"New Insights ({len(result.new_insights)})", "-" * 20])
        for insight in result.new_insights[:10]:
            lines.append(
                f"  [{insight.insight_type.value}] "
                f"(conf={insight.confidence:.2f}) {insight.description[:80]}"
            )
        if len(result.new_insights) > 10:
            lines.append(f"  ... and {len(result.new_insights) - 10} more")

    if result.updated_insights:
        lines.extend(
            ["", f"Updated Insights ({len(result.updated_insights)})", "-" * 20]
        )
        for insight in result.updated_insights[:5]:
            lines.append(
                f"  [{insight.insight_type.value}] "
                f"(conf={insight.confidence:.2f}) {insight.description[:80]}"
            )
        if len(result.updated_insights) > 5:
            lines.append(f"  ... and {len(result.updated_insights) - 5} more")

    return "\n".join(lines)


def _write_output(content: str, output_path: str | None) -> None:
    """Write content to stdout or a file.

    Args:
        content: String content to write.
        output_path: File path or None for stdout.

    Raises:
        SystemExit(1): On write failure.
    """
    if output_path is None:
        print(content)
        return

    try:
        Path(output_path).write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"Error: failed to write output to {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point for pattern_extraction_compute.

    Parses CLI arguments, loads input JSON, runs extraction, and
    writes results. Exits with code 0 on success, 1 on input error,
    2 on extraction failure.
    """
    parser = _build_parser()
    args = parser.parse_args()

    # Load and validate input
    raw = _load_input(args.input)
    input_data = _build_input(raw, args)

    # Run extraction
    try:
        result = extract_all_patterns(input_data)
    except Exception as exc:
        print(f"Error: extraction failed: {exc}", file=sys.stderr)
        sys.exit(2)

    # Format and write output
    if args.output_format == "summary":
        content = _format_summary(result)
    else:
        content = json.dumps(
            result.model_dump(mode="json"),
            indent=args.indent,
            default=str,
        )

    _write_output(content, args.output)


if __name__ == "__main__":
    main()
