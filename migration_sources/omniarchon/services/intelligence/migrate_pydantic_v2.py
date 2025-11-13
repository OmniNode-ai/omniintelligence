#!/usr/bin/env python3
"""
Pydantic V2 Migration Script

Migrates deprecated Pydantic V1 patterns to V2:
- class Config: → model_config = ConfigDict(...)
- @validator → @field_validator
- @root_validator → @model_validator

Usage:
    python migrate_pydantic_v2.py [--dry-run] [--verbose]
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set


class PydanticV2Migrator:
    """Migrates Pydantic V1 patterns to V2."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.stats = {
            "files_scanned": 0,
            "files_modified": 0,
            "config_blocks_migrated": 0,
            "validators_migrated": 0,
            "root_validators_migrated": 0,
            "imports_added": 0,
        }
        self.modified_files: Set[Path] = set()

    def log(self, message: str) -> None:
        """Log verbose message."""
        if self.verbose:
            print(f"  {message}")

    def migrate_config_block(self, content: str, file_path: Path) -> str:
        """
        Migrate class Config: blocks to model_config = ConfigDict(...)

        Handles:
        - frozen = True/False
        - json_schema_extra = {...}
        - schema_extra = {...}
        - arbitrary_types_allowed = True
        - json_encoders = {...} (deprecated, remove)
        - use_enum_values = False
        """
        lines = content.split("\n")
        new_lines = []
        i = 0
        config_migrated = False

        while i < len(lines):
            line = lines[i]

            # Look for "class Config:" pattern
            if re.match(r"^\s+class Config:\s*$", line):
                indent = len(line) - len(line.lstrip())
                base_indent = " " * indent

                # Extract Config block
                config_lines = []
                i += 1

                # Skip docstring if present
                if i < len(lines) and '"""' in lines[i]:
                    # Skip until closing docstring
                    while i < len(lines) and not (
                        lines[i].count('"""') >= 2
                        or (config_lines and '"""' in lines[i])
                    ):
                        i += 1
                    i += 1  # Skip closing """

                # Collect Config attributes
                while i < len(lines):
                    current = lines[i]
                    # Empty line or start of next class/function means end of Config
                    if not current.strip() or (
                        current.strip()
                        and len(current) - len(current.lstrip()) <= indent
                    ):
                        if current.strip() and not current.strip().startswith("#"):
                            break
                    if current.strip():
                        config_lines.append(current)
                    i += 1

                # Parse Config attributes
                config_dict = {}
                json_schema_content = []
                in_json_schema = False
                brace_depth = 0

                for config_line in config_lines:
                    stripped = config_line.strip()

                    # Handle frozen
                    if match := re.match(r"frozen\s*=\s*(True|False)", stripped):
                        config_dict["frozen"] = match.group(1)

                    # Handle arbitrary_types_allowed
                    elif match := re.match(
                        r"arbitrary_types_allowed\s*=\s*(True|False)", stripped
                    ):
                        config_dict["arbitrary_types_allowed"] = match.group(1)

                    # Handle use_enum_values
                    elif match := re.match(
                        r"use_enum_values\s*=\s*(True|False)", stripped
                    ):
                        config_dict["use_enum_values"] = match.group(1)

                    # Handle json_schema_extra or schema_extra
                    elif "json_schema_extra" in stripped or "schema_extra" in stripped:
                        in_json_schema = True
                        json_schema_content.append(config_line)
                        brace_depth = stripped.count("{") - stripped.count("}")

                    # Continue collecting json_schema_extra
                    elif in_json_schema:
                        json_schema_content.append(config_line)
                        brace_depth += stripped.count("{") - stripped.count("}")
                        if brace_depth <= 0:
                            in_json_schema = False

                    # Skip deprecated json_encoders
                    elif "json_encoders" in stripped:
                        self.log(f"Skipping deprecated json_encoders in {file_path}")
                        # Skip until closing brace
                        depth = stripped.count("{") - stripped.count("}")
                        j = config_lines.index(config_line) + 1
                        while j < len(config_lines) and depth > 0:
                            depth += config_lines[j].count("{") - config_lines[j].count(
                                "}"
                            )
                            j += 1

                # Build model_config line
                if config_dict or json_schema_content:
                    config_parts = []

                    # Add simple attributes
                    for key, value in config_dict.items():
                        config_parts.append(f"{key}={value}")

                    # Add json_schema_extra if present
                    if json_schema_content:
                        # Extract the dict content
                        schema_str = "\n".join(json_schema_content)
                        # Normalize to json_schema_extra
                        schema_str = schema_str.replace(
                            "schema_extra", "json_schema_extra"
                        )
                        # Extract just the dict part
                        if match := re.search(
                            r"(json_schema_extra\s*=\s*\{.*\})", schema_str, re.DOTALL
                        ):
                            config_parts.append(match.group(1).strip())

                    # Create model_config line
                    if config_parts:
                        if len(config_parts) == 1 and not json_schema_content:
                            # Single simple attribute
                            new_lines.append(
                                f"{base_indent}model_config = ConfigDict({config_parts[0]})"
                            )
                        else:
                            # Multiple attributes or complex json_schema_extra
                            new_lines.append(f"{base_indent}model_config = ConfigDict(")
                            for j, part in enumerate(config_parts):
                                comma = "," if j < len(config_parts) - 1 else ""
                                if "json_schema_extra" in part:
                                    # Multi-line json_schema_extra
                                    new_lines.append(f"{base_indent}    {part}{comma}")
                                else:
                                    new_lines.append(f"{base_indent}    {part}{comma}")
                            new_lines.append(f"{base_indent})")

                        config_migrated = True
                        self.stats["config_blocks_migrated"] += 1
                        self.log(f"Migrated Config block in {file_path}")

                continue

            new_lines.append(line)
            i += 1

        return "\n".join(new_lines)

    def ensure_configdict_import(self, content: str, file_path: Path) -> str:
        """Ensure ConfigDict is imported from pydantic."""
        # Check if already imported
        if "ConfigDict" in content and "from pydantic import" in content:
            # Check if ConfigDict is in the import
            import_pattern = r"from pydantic import ([^;\n]+)"
            for match in re.finditer(import_pattern, content):
                imports = match.group(1)
                if "ConfigDict" in imports:
                    return content  # Already imported

        # Find the pydantic import line
        lines = content.split("\n")
        new_lines = []
        import_added = False

        for i, line in enumerate(lines):
            if (
                not import_added
                and "from pydantic import" in line
                and "ConfigDict" not in line
            ):
                # Add ConfigDict to import
                # Handle multi-line imports
                if "(" in line:
                    # Multi-line import with parentheses
                    new_lines.append(line)
                    # Find closing paren
                    j = i + 1
                    while j < len(lines) and ")" not in lines[j]:
                        new_lines.append(lines[j])
                        j += 1
                    # Add ConfigDict before closing paren
                    closing_line = lines[j]
                    new_lines.append("    ConfigDict,")
                    new_lines.append(closing_line)
                    import_added = True
                    # Skip the lines we already processed
                    for _ in range(j - i):
                        next(enumerate(lines[i + 1 :], i + 1), None)
                else:
                    # Single-line import
                    line = line.rstrip()
                    if line.endswith(","):
                        new_lines.append(line)
                        new_lines.append("    ConfigDict,")
                    else:
                        # Add ConfigDict to the import
                        new_lines.append(line.rstrip() + ", ConfigDict")
                    import_added = True
            else:
                new_lines.append(line)

        if import_added:
            self.stats["imports_added"] += 1
            self.log(f"Added ConfigDict import to {file_path}")

        return "\n".join(new_lines)

    def migrate_file(self, file_path: Path) -> bool:
        """Migrate a single file. Returns True if file was modified."""
        try:
            content = file_path.read_text(encoding="utf-8")
            original_content = content

            # Skip if no Config blocks
            if "class Config:" not in content:
                return False

            self.log(f"Processing {file_path}")

            # Migrate Config blocks
            content = self.migrate_config_block(content, file_path)

            # Add ConfigDict import if needed
            if content != original_content:
                content = self.ensure_configdict_import(content, file_path)

            # Write back if modified
            if content != original_content:
                if not self.dry_run:
                    file_path.write_text(content, encoding="utf-8")
                self.modified_files.add(file_path)
                self.stats["files_modified"] += 1
                return True

            return False

        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            return False

    def migrate_directory(self, directory: Path) -> None:
        """Migrate all Python files in directory."""
        python_files = list(directory.rglob("*.py"))

        for file_path in python_files:
            # Skip __pycache__ and test files for now
            if "__pycache__" in str(file_path):
                continue

            self.stats["files_scanned"] += 1
            self.migrate_file(file_path)

    def print_summary(self) -> None:
        """Print migration summary."""
        print("\n" + "=" * 60)
        print("Pydantic V2 Migration Summary")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Files scanned: {self.stats['files_scanned']}")
        print(f"Files modified: {self.stats['files_modified']}")
        print(f"Config blocks migrated: {self.stats['config_blocks_migrated']}")
        print(f"ConfigDict imports added: {self.stats['imports_added']}")
        print(f"@validator decorators migrated: {self.stats['validators_migrated']}")
        print(
            f"@root_validator decorators migrated: {self.stats['root_validators_migrated']}"
        )

        if self.modified_files and self.verbose:
            print("\nModified files:")
            for file_path in sorted(self.modified_files):
                print(f"  - {file_path}")

        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No files were actually modified")
        else:
            print("\n✅ Migration complete!")


def main():
    """Main migration entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Pydantic V1 to V2 patterns")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed progress"
    )
    parser.add_argument(
        "--directory",
        "-d",
        type=Path,
        default=Path("src"),
        help="Directory to migrate (default: src)",
    )

    args = parser.parse_args()

    migrator = PydanticV2Migrator(dry_run=args.dry_run, verbose=args.verbose)

    print(f"Starting Pydantic V2 migration...")
    print(f"Target directory: {args.directory}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    migrator.migrate_directory(args.directory)
    migrator.print_summary()


if __name__ == "__main__":
    main()
