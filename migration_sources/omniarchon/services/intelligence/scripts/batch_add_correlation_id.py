#!/usr/bin/env python3
"""
Batch add correlation_id to multiple files.

Processes all files from the coverage report and adds correlation_id support
to API routes and service methods.

Usage:
    python scripts/batch_add_correlation_id.py [--dry-run] [--priority CRITICAL|HIGH|ALL]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set


def get_files_without_correlation_id() -> tuple[Dict[str, List[str]], Dict]:
    """Get categorized files without correlation_id."""
    result = subprocess.run(
        ["python3", "scripts/correlation_id_coverage.py", "--json"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Error running coverage script", file=sys.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)
    categories = {cat: info["files"] for cat, info in data["categories"].items()}
    stats = data["statistics"]

    return categories, stats


def add_correlation_id_to_file(
    file_path: str, dry_run: bool = False
) -> tuple[bool, List[str]]:
    """Add correlation_id support to a single file."""
    path = Path(file_path)

    if not path.exists():
        return False, [f"File not found: {file_path}"]

    try:
        content = path.read_text()
        original_content = content
        changes = []

        # 1. Add UUID import if needed
        if "from uuid import" not in content and "import uuid" not in content:
            # Find last import line
            lines = content.split("\n")
            last_import_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    last_import_idx = i

            if last_import_idx > 0:
                lines.insert(last_import_idx + 1, "from uuid import UUID, uuid4")
                content = "\n".join(lines)
                changes.append("Added UUID import")
        elif "UUID" not in content or "uuid4" not in content:
            # Update existing import
            content = re.sub(
                r"from uuid import ([^\n]+)",
                lambda m: (
                    f"from uuid import {m.group(1).rstrip(',')}, UUID, uuid4"
                    if "UUID" not in m.group(1)
                    else m.group(0)
                ),
                content,
            )

        # 2. Add correlation_id to FastAPI routes
        route_pattern = r"@router\.(get|post|put|delete|patch)\([^\)]+\)\s*async def (\w+)\s*\(([^)]*)\)"

        def add_to_route(match):
            method = match.group(1)
            func_name = match.group(2)
            params = match.group(3)

            if "correlation_id" in params:
                return match.group(0)

            # Add correlation_id parameter
            if params.strip() and not params.strip().endswith(","):
                new_params = (
                    params.rstrip() + ",\n    correlation_id: Optional[UUID] = None"
                )
            else:
                new_params = (
                    params.rstrip(", ") + "\n    correlation_id: Optional[UUID] = None"
                )

            result = f'@router.{method}({match.group(0).split("(", 1)[1].split(")", 1)[0]})\nasync def {func_name}(\n{new_params}\n)'
            changes.append(f"Added correlation_id to route {func_name}")
            return result

        # Apply route modifications
        if "@router." in content:
            original = content
            content = re.sub(route_pattern, add_to_route, content, flags=re.DOTALL)

        # 3. Add correlation_id to service methods (async def methods)
        service_pattern = r"(async def (\w+)\s*\(self,\s*)([^)]*?)(\s*\)\s*->)"

        def add_to_service(match):
            prefix = match.group(1)
            method_name = match.group(2)
            params = match.group(3)
            suffix = match.group(4)

            if "correlation_id" in match.group(0):
                return match.group(0)

            # Add correlation_id
            if params.strip():
                new_params = (
                    params.rstrip(", ")
                    + ",\n        correlation_id: Optional[UUID] = None"
                )
            else:
                new_params = "correlation_id: Optional[UUID] = None"

            changes.append(f"Added correlation_id to method {method_name}")
            return f"{prefix}{new_params}{suffix}"

        if "async def " in content and "(self," in content:
            content = re.sub(service_pattern, add_to_service, content, flags=re.DOTALL)

        # 4. Ensure Optional is imported from typing
        if "Optional[UUID]" in content and "from typing import" in content:
            if "Optional" not in re.search(
                r"from typing import ([^\n]+)", content
            ).group(1):
                content = re.sub(
                    r"from typing import ([^\n]+)",
                    lambda m: f"from typing import {m.group(1).rstrip(',')}, Optional",
                    content,
                )
                changes.append("Added Optional to typing imports")

        # Write changes
        if content != original_content:
            if not dry_run:
                path.write_text(content)
            return True, changes
        else:
            return False, ["No changes needed"]

    except Exception as e:
        return False, [f"Error: {str(e)}"]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch add correlation_id to multiple files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )
    parser.add_argument(
        "--priority",
        choices=["CRITICAL", "HIGH", "ALL"],
        default="CRITICAL",
        help="Priority level to process (default: CRITICAL)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print(f"🔍 Getting files without correlation_id...")
    categories, stats = get_files_without_correlation_id()

    # Determine which files to process
    files_to_process: Set[str] = set()

    if args.priority == "CRITICAL":
        # Process CRITICAL files only
        files_to_process.update(categories.get("api_routes", []))
        files_to_process.update(categories.get("event_handlers", []))
        files_to_process.update(categories.get("background_tasks", []))
    elif args.priority == "HIGH":
        # Process CRITICAL + HIGH files
        files_to_process.update(categories.get("api_routes", []))
        files_to_process.update(categories.get("event_handlers", []))
        files_to_process.update(categories.get("background_tasks", []))
        files_to_process.update(categories.get("services", []))
    else:  # ALL
        for category_files in categories.values():
            files_to_process.update(category_files)

    print(f"\n📊 Processing {len(files_to_process)} files ({args.priority} priority)")
    if args.dry_run:
        print("   [DRY RUN MODE - no changes will be written]")
    print()

    # Process files
    success_count = 0
    skip_count = 0
    error_count = 0

    for file_path in sorted(files_to_process):
        success, changes = add_correlation_id_to_file(file_path, dry_run=args.dry_run)

        if success:
            success_count += 1
            print(f"✅ {file_path}")
            if args.verbose:
                for change in changes:
                    print(f"   - {change}")
        elif "No changes needed" in changes[0]:
            skip_count += 1
            if args.verbose:
                print(f"⏭️  {file_path} (no changes needed)")
        else:
            error_count += 1
            print(f"❌ {file_path}: {changes[0]}")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files processed: {len(files_to_process)}")
    print(f"  ✅ Modified: {success_count}")
    print(f"  ⏭️  Skipped: {skip_count}")
    print(f"  ❌ Errors: {error_count}")
    print()

    # Run coverage check again
    print("🔄 Running coverage check...")
    subprocess.run(["python3", "scripts/correlation_id_coverage.py"])


if __name__ == "__main__":
    main()
