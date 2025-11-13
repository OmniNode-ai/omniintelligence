#!/usr/bin/env python3
"""
Unified log viewer for Archon pipeline.

Usage:
    # View all logs
    python3 scripts/view_pipeline_logs.py

    # Trace specific correlation ID
    python3 scripts/view_pipeline_logs.py --correlation-id abc-123

    # Show only errors
    python3 scripts/view_pipeline_logs.py --level ERROR

    # Real-time tail
    python3 scripts/view_pipeline_logs.py --follow

    # Specific service
    python3 scripts/view_pipeline_logs.py --service archon-intelligence

    # Filter by emoji
    python3 scripts/view_pipeline_logs.py --filter "❌"
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from typing import Dict, List

# ANSI color codes
COLORS = {
    "ERROR": "\033[91m",  # Red
    "WARNING": "\033[93m",  # Yellow
    "INFO": "\033[92m",  # Green
    "DEBUG": "\033[94m",  # Blue
    "RESET": "\033[0m",
}

SERVICES = [
    "archon-intelligence-consumer-1",
    "archon-intelligence-consumer-2",
    "archon-intelligence-consumer-3",
    "archon-intelligence-consumer-4",
    "archon-intelligence",
    "archon-bridge",
    "archon-kafka-consumer",
    "archon-search",
]


def get_docker_logs(
    service: str, since: str = None, follow: bool = False, tail: int = 100
) -> List[str]:
    """Get logs from a Docker service."""
    cmd = ["docker", "logs"]

    if since:
        cmd.extend(["--since", since])
    if follow:
        cmd.append("-f")
    if tail:
        cmd.extend(["--tail", str(tail)])

    cmd.append(service)

    try:
        result = subprocess.run(cmd, capture_output=not follow, text=True, check=False)
        if follow:
            return []

        # FIX: Capture both stdout and stderr (Docker logs write to stderr)
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr

        return output.split("\n") if output else []
    except Exception as e:
        return [f"Error getting logs for {service}: {e}"]


def parse_log_line(line: str, service: str) -> Dict:
    """Parse a log line into structured format."""
    timestamp = datetime.now().isoformat()
    level = "INFO"
    message = line

    # Try to extract timestamp
    ts_match = re.match(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", line)
    if ts_match:
        timestamp = ts_match.group(1)

    # Extract log level
    for lvl in ["ERROR", "WARNING", "INFO", "DEBUG"]:
        if lvl in line.upper():
            level = lvl
            break

    # Try to parse as JSON
    try:
        if line.strip().startswith("{"):
            data = json.loads(line)
            return {
                "timestamp": data.get("timestamp", timestamp),
                "service": service,
                "level": data.get("level", level),
                "message": data.get("message", line),
                "extra": data.get("extra", {}),
                "raw": line,
            }
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return {
        "timestamp": timestamp,
        "service": service,
        "level": level,
        "message": message,
        "extra": {},
        "raw": line,
    }


def format_log_line(log: Dict, colorize: bool = True) -> str:
    """Format a log entry for display."""
    color = COLORS.get(log["level"], "") if colorize else ""
    reset = COLORS["RESET"] if colorize else ""

    service_name = log["service"][:20].ljust(20)
    timestamp = log["timestamp"][:19]
    level = log["level"][:7].ljust(7)
    message = log["message"]

    # Add correlation_id if present
    correlation_id = log["extra"].get("correlation_id", "")
    if correlation_id:
        correlation_id = f"[{correlation_id[:8]}]"

    return (
        f"{color}{timestamp} | {service_name} | {level} | "
        f"{correlation_id} {message}{reset}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Unified log viewer for Archon pipeline"
    )
    parser.add_argument("--service", help="Filter by service name")
    parser.add_argument("--correlation-id", help="Filter by correlation ID")
    parser.add_argument(
        "--level",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        help="Filter by log level",
    )
    parser.add_argument(
        "--filter", help="Filter by text/emoji (e.g., '❌' or 'intelligence')"
    )
    parser.add_argument("--since", help="Show logs since time (e.g., '1h', '30m')")
    parser.add_argument(
        "--follow", "-f", action="store_true", help="Follow logs in real-time"
    )
    parser.add_argument(
        "--tail", type=int, default=100, help="Number of lines to show (default: 100)"
    )
    parser.add_argument("--no-color", action="store_true", help="Disable color output")

    args = parser.parse_args()

    # Filter services
    services = SERVICES
    if args.service:
        services = [s for s in services if args.service in s]

    print(f"📋 Viewing logs from {len(services)} services...")
    print(f"   Services: {', '.join(services)}")
    if args.correlation_id:
        print(f"   Correlation ID: {args.correlation_id}")
    if args.level:
        print(f"   Level: {args.level}")
    if args.filter:
        print(f"   Filter: {args.filter}")
    print()

    # Collect and merge logs
    all_logs = []
    for service in services:
        logs = get_docker_logs(
            service, since=args.since, follow=args.follow, tail=args.tail
        )
        for line in logs:
            if not line.strip():
                continue

            log = parse_log_line(line, service)

            # Apply filters
            if args.level and log["level"] != args.level:
                continue
            if args.correlation_id and args.correlation_id not in str(
                log.get("extra", {})
            ):
                continue
            if args.filter and args.filter not in log["raw"]:
                continue

            all_logs.append(log)

    # Sort by timestamp
    all_logs.sort(key=lambda x: x["timestamp"])

    # Display
    for log in all_logs:
        print(format_log_line(log, colorize=not args.no_color))

    print(f"\n📊 Displayed {len(all_logs)} log entries")


if __name__ == "__main__":
    main()
