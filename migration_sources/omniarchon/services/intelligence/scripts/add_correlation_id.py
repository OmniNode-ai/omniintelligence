#!/usr/bin/env python3
"""
Automated script to add correlation_id support to Python files.

This script adds correlation_id parameters and logging to common patterns:
- API route handlers
- Service methods
- Event handlers
- Background tasks

Usage:
    python scripts/add_correlation_id.py <file_path> [--dry-run]
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


class CorrelationIDAdder:
    """Add correlation_id support to Python files."""

    def __init__(self, file_path: Path, dry_run: bool = False):
        self.file_path = file_path
        self.dry_run = dry_run
        self.changes_made = []

    def read_file(self) -> str:
        """Read file content."""
        return self.file_path.read_text()

    def write_file(self, content: str) -> None:
        """Write file content."""
        if not self.dry_run:
            self.file_path.write_text(content)

    def add_uuid_import(self, content: str) -> str:
        """Add UUID import if not present."""
        if "from uuid import" in content or "import uuid" in content:
            # Already has UUID import
            if "UUID" not in content or "uuid4" not in content:
                # Need to add UUID or uuid4
                import_match = re.search(r"from uuid import ([^\n]+)", content)
                if import_match:
                    imports = import_match.group(1)
                    needed = []
                    if "UUID" not in imports:
                        needed.append("UUID")
                    if "uuid4" not in imports:
                        needed.append("uuid4")

                    if needed:
                        new_imports = imports.rstrip(",") + ", " + ", ".join(needed)
                        content = content.replace(
                            f"from uuid import {imports}",
                            f"from uuid import {new_imports}",
                        )
                        self.changes_made.append("Updated UUID imports")
            return content

        # Add new import
        # Find the last import line
        import_lines = []
        for line in content.split("\n"):
            if line.startswith("import ") or line.startswith("from "):
                import_lines.append(line)

        if import_lines:
            last_import = import_lines[-1]
            content = content.replace(
                last_import, last_import + "\nfrom uuid import UUID, uuid4", 1
            )
            self.changes_made.append("Added UUID import")

        return content

    def add_correlation_to_fastapi_route(self, content: str) -> str:
        """Add correlation_id to FastAPI route handlers."""
        # Pattern: @router.get/post/put/delete
        # Find function definitions after router decorators

        pattern = r"(@router\.(get|post|put|delete|patch)\([^\)]+\)\s*(?:async )?def\s+(\w+)\s*\([^)]*\))"

        def add_correlation_param(match):
            full_match = match.group(0)

            # Skip if already has correlation_id
            if "correlation_id" in full_match:
                return full_match

            # Find the function signature
            func_pattern = r"(def\s+\w+\s*\()([^)]*)\)"
            func_match = re.search(func_pattern, full_match)

            if not func_match:
                return full_match

            func_start = func_match.group(1)
            params = func_match.group(2)

            # Add correlation_id parameter
            if params.strip():
                new_params = (
                    params.rstrip(", ") + ",\n    correlation_id: Optional[UUID] = None"
                )
            else:
                new_params = "correlation_id: Optional[UUID] = None"

            new_signature = f"{func_start}{new_params})"
            result = full_match.replace(f"{func_start}{params})", new_signature)

            self.changes_made.append(f"Added correlation_id to route handler")
            return result

        content = re.sub(
            pattern, add_correlation_param, content, flags=re.MULTILINE | re.DOTALL
        )
        return content

    def add_correlation_to_service_methods(self, content: str) -> str:
        """Add correlation_id to service class methods."""
        # Pattern: async def method_name(self, ...):

        pattern = r"(async\s+def\s+(\w+)\s*\(self,\s*)([^)]*)\)(\s*->\s*[^:]+)?:"

        def add_param(match):
            full_start = match.group(1)  # "async def method(self, "
            method_name = match.group(2)
            params = match.group(3)
            return_type = match.group(4) or ""

            # Skip special methods
            if method_name.startswith("__") or method_name in [
                "initialize",
                "shutdown",
                "health_check",
            ]:
                # Still add correlation_id to these
                pass

            # Skip if already has correlation_id
            if "correlation_id" in params:
                return match.group(0)

            # Add correlation_id parameter
            if params.strip():
                new_params = (
                    params.rstrip(", ")
                    + ",\n        correlation_id: Optional[UUID] = None"
                )
            else:
                new_params = "correlation_id: Optional[UUID] = None"

            result = f"{full_start}{new_params}){return_type}:"
            self.changes_made.append(f"Added correlation_id to method {method_name}")
            return result

        content = re.sub(pattern, add_param, content, flags=re.MULTILINE)
        return content

    def add_logger_statements(self, content: str) -> str:
        """Add correlation_id to logger statements where missing."""
        # Pattern: logger.info/warning/error without correlation_id

        pattern = r"(logger\.(info|warning|error|debug)\s*\([^)]+\))"

        def add_correlation(match):
            statement = match.group(0)

            # Skip if already has correlation_id
            if "correlation_id" in statement or "extra=" in statement:
                return statement

            # Add extra parameter with correlation_id
            if statement.endswith(")"):
                new_statement = (
                    statement[:-1] + ', extra={"correlation_id": str(correlation_id)})'
                )
                return new_statement

            return statement

        # Only add if correlation_id is in scope (has parameter)
        if (
            "correlation_id: Optional[UUID]" in content
            or "correlation_id = " in content
        ):
            content = re.sub(pattern, add_correlation, content)
            self.changes_made.append("Added correlation_id to logger statements")

        return content

    def process_file(self) -> Tuple[bool, List[str]]:
        """Process the file and add correlation_id support."""
        try:
            content = self.read_file()
            original_content = content

            # Apply transformations
            content = self.add_uuid_import(content)
            content = self.add_correlation_to_fastapi_route(content)
            content = self.add_correlation_to_service_methods(content)
            # Note: Logger statements require more context, skip for now

            # Write changes
            if content != original_content:
                self.write_file(content)
                return True, self.changes_made
            else:
                return False, ["No changes needed"]

        except Exception as e:
            return False, [f"Error: {str(e)}"]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add correlation_id support to Python files"
    )
    parser.add_argument("file_path", type=Path, help="Path to Python file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )

    args = parser.parse_args()

    if not args.file_path.exists():
        print(f"Error: File not found: {args.file_path}", file=sys.stderr)
        sys.exit(1)

    adder = CorrelationIDAdder(args.file_path, dry_run=args.dry_run)
    success, changes = adder.process_file()

    if success:
        print(f"✅ Processed: {args.file_path}")
        for change in changes:
            print(f"  - {change}")
    else:
        print(f"⚠️  {args.file_path}: {changes[0]}")


if __name__ == "__main__":
    main()
