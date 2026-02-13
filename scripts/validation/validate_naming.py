#!/usr/bin/env python3
"""Naming convention validation for omniintelligence.

Validates that Python files and classes follow ONEX naming conventions
for the omniintelligence codebase.

Intelligence-Specific Conventions:
    - handlers/ -> handler_*.py, Handler* classes
    - models/ -> model_*.py, Model* classes
    - nodes/ -> node_*.py (directories), node.py (main file)
    - runtime/ -> plugin.py, wiring.py, dispatch_*.py, contract_*.py
    - tools/ -> tool_*.py (or descriptive names)

Ported from omnibase_infra with omniintelligence-specific rules.

Usage:
    python scripts/validation/validate_naming.py
    python scripts/validation/validate_naming.py src/omniintelligence
    python scripts/validation/validate_naming.py --verbose

Exit Codes:
    0 - All naming conventions are compliant
    1 - Naming violations detected
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

# =============================================================================
# omniintelligence-specific directory prefix rules
# =============================================================================

INTELLIGENCE_DIRECTORY_PREFIX_RULES: dict[str, frozenset[str]] = {
    "handlers": frozenset(
        {"handler_", "protocol_", "model_", "enum_", "adapter_", "registry_"}
    ),
    "models": frozenset({"model_", "enum_", "protocol_", "types_"}),
    "enums": frozenset({"enum_"}),
    "protocols": frozenset({"protocol_"}),
    "runtime": frozenset(
        {
            "plugin",
            "wiring",
            "dispatch_",
            "contract_",
            "handler_",
            "service_",
            "registry_",
            "model_",
            "message_",
            "stub_",
            "adapter",
        }
    ),
    "nodes": frozenset(
        {
            "node_",
            "node.py",
            "model_",
            "handler_",
            "registry_",
            "enum_",
            "protocol_",
            "protocols",
            "error_codes",
            "test_",
        }
    ),
    "tools": frozenset(
        {
            "tool_",
            "contract_",
            "validate_",
            "generate_",
        }
    ),
}

INTELLIGENCE_ALLOWED_FILES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "conftest.py",
        "py.typed",
        "node.py",
        "contract.yaml",
        "README.md",
        "presets.py",
        "exceptions.py",
        "constants.py",
        "introspection.py",
        "contract_loader.py",
    }
)

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024


@dataclass
class NamingViolation:
    """A naming convention violation."""

    file_path: str
    line_number: int
    class_name: str
    expected_pattern: str
    description: str
    severity: str = "error"


@dataclass
class ParsedFileInfo:
    """Cached parsed Python file info."""

    file_path: Path
    ast_tree: ast.Module | None
    class_defs: list[tuple[str, int]] = field(default_factory=list)
    parse_error: str | None = None
    relevant_dir: str | None = None


class IntelligenceNamingConventionValidator:
    """Validates naming conventions for omniintelligence codebase."""

    NAMING_PATTERNS: ClassVar[dict[str, dict[str, str | None]]] = {
        "handlers": {
            "pattern": r"^Handler[A-Z][A-Za-z0-9]*$",
            "file_prefix": "handler_",
            "description": "Handlers must start with 'Handler' (e.g., HandlerClaudeHookEvent)",
            "directory": "handlers",
        },
        "models": {
            "pattern": r"^Model[A-Z][A-Za-z0-9]*$",
            "file_prefix": "model_",
            "description": "Models must start with 'Model' (e.g., ModelPatternExtractionInput)",
            "directory": "models",
        },
        "enums": {
            "pattern": r"^Enum[A-Z][A-Za-z0-9]*$",
            "file_prefix": "enum_",
            "description": "Enums must start with 'Enum' (e.g., EnumPatternLifecycleStatus)",
            "directory": None,
        },
        "protocols": {
            "pattern": r"^Protocol[A-Z][A-Za-z0-9]*$",
            "file_prefix": "protocol_",
            "description": "Protocols must start with 'Protocol' (e.g., ProtocolKafkaPublisher)",
            "directory": "protocols",
        },
        "registries": {
            "pattern": r"^Registry[A-Z][A-Za-z0-9]*$",
            "file_prefix": "registry_",
            "description": "Registries must start with 'Registry' (e.g., RegistryPatternPromotionEffect)",
            "directory": None,
        },
    }

    EXCEPTION_PATTERNS: ClassVar[list[str]] = [
        r"^_.*",
        r".*Test$",
        r".*TestCase$",
        r"^Test.*",
        r".*Error$",
        r".*Exception$",
        r".*Config$",
        r".*Result$",
        r".*Response$",
        r".*Dict$",
    ]

    _COMPILED_EXCEPTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(pattern) for pattern in EXCEPTION_PATTERNS
    ]

    _COMPILED_NAMING_PATTERNS: ClassVar[dict[str, re.Pattern[str]]] = {}

    ARCHITECTURAL_EXEMPTIONS: ClassVar[dict[str, list[str]]] = {
        "runtime/": [
            "Handler*",
            "Registry*",
            "*Engine",
            "*Plugin",
            "*Wiring",
        ],
        "handlers/": [
            "Handler*",
            "Adapter*",
        ],
        "models/": [
            "Model*",
            "Enum*",
            "Registry*",
        ],
        "nodes/": [
            "Handler*",
            "Node*",
            "Registry*",
        ],
        "tools/": [
            "*Linter",
            "*Validator",
            "*Reporter",
        ],
    }

    @classmethod
    def _ensure_compiled_patterns(cls) -> None:
        if cls._COMPILED_NAMING_PATTERNS:
            return
        for category, rules in cls.NAMING_PATTERNS.items():
            pattern = rules.get("pattern")
            if pattern:
                cls._COMPILED_NAMING_PATTERNS[category] = re.compile(pattern)

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()
        self.violations: list[NamingViolation] = []
        self._file_cache: dict[Path, ParsedFileInfo] = {}
        self._all_python_files: list[Path] | None = None
        self._skipped_large_files: list[tuple[Path, int]] = []
        self._validated_file_categories: set[tuple[Path, str]] = set()
        self._ensure_compiled_patterns()

    def check_file_name(self, file_path: Path) -> tuple[str | None, str]:
        """Check if a file name conforms to naming conventions."""
        file_name = file_path.name

        if not file_name.endswith(".py"):
            return None, "info"

        if file_name in INTELLIGENCE_ALLOWED_FILES:
            return None, "info"

        if file_name.startswith("_"):
            return None, "info"

        parts = file_path.parts
        try:
            idx = parts.index("omniintelligence")
            if idx + 1 < len(parts) - 1:
                relevant_dir = parts[idx + 1]

                # For nodes/, only apply prefix rules to files in the immediate
                # node directories (depth 1-2 under nodes/), not deeply nested
                # handler/model utility files. Files in handlers/, models/, etc.
                # subdirectories within a node follow their own conventions.
                if relevant_dir == "nodes":
                    # Calculate depth: nodes/node_foo/node.py = depth 2
                    # nodes/node_foo/handlers/utils.py = depth 3+
                    depth_from_nodes = len(parts) - (idx + 2)
                    if depth_from_nodes > 2:
                        # Deeply nested file — skip node-level prefix check.
                        # These files follow their parent directory conventions.
                        return None, "info"

                required_prefixes = INTELLIGENCE_DIRECTORY_PREFIX_RULES.get(
                    relevant_dir
                )
                if required_prefixes:
                    matches_prefix = False
                    for prefix in required_prefixes:
                        if file_name.startswith(prefix) or file_name == prefix:
                            matches_prefix = True
                            break

                    if not matches_prefix:
                        prefix_list = sorted(required_prefixes)[:3]
                        if len(required_prefixes) == 1:
                            prefix_str = f"'{prefix_list[0]}'"
                        elif len(required_prefixes) > 3:
                            prefix_str = f"one of {prefix_list}..."
                        else:
                            prefix_str = f"one of {sorted(required_prefixes)}"
                        return (
                            f"File '{file_name}' in '{relevant_dir}/' should start "
                            f"with {prefix_str}",
                            "warning",
                        )
        except ValueError:
            pass

        return None, "info"

    def _get_all_python_files(self) -> list[Path]:
        """Get all Python files, cached."""
        if self._all_python_files is None:
            self._all_python_files = []
            for file_path in self.repo_path.rglob("*.py"):
                if "__pycache__" in file_path.parts:
                    continue
                if "_legacy" in file_path.parts:
                    continue
                if file_path.is_symlink():
                    continue
                try:
                    file_size = file_path.stat().st_size
                    if file_size > MAX_FILE_SIZE_BYTES:
                        self._skipped_large_files.append(
                            (file_path.resolve(), file_size)
                        )
                        continue
                except OSError:
                    continue
                self._all_python_files.append(file_path.resolve())
        return self._all_python_files

    def _get_parsed_file_info(self, file_path: Path) -> ParsedFileInfo:
        """Get cached parsed file info."""
        if file_path not in self._file_cache:
            try:
                try:
                    file_size = file_path.stat().st_size
                except OSError as stat_error:
                    self._file_cache[file_path] = ParsedFileInfo(
                        file_path=file_path,
                        ast_tree=None,
                        parse_error=f"Cannot access file: {stat_error}",
                    )
                    return self._file_cache[file_path]

                if file_size > MAX_FILE_SIZE_BYTES:
                    self._file_cache[file_path] = ParsedFileInfo(
                        file_path=file_path,
                        ast_tree=None,
                        parse_error="File too large",
                    )
                    return self._file_cache[file_path]

                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=str(file_path))
                class_defs: list[tuple[str, int]] = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_defs.append((node.name, node.lineno))

                relevant_dir: str | None = None
                parts = file_path.parts
                try:
                    idx = parts.index("omniintelligence")
                    if idx + 1 < len(parts) - 1:
                        relevant_dir = parts[idx + 1]
                except ValueError:
                    pass

                self._file_cache[file_path] = ParsedFileInfo(
                    file_path=file_path,
                    ast_tree=tree,
                    class_defs=class_defs,
                    relevant_dir=relevant_dir,
                )

            except (SyntaxError, UnicodeDecodeError, OSError) as e:
                self._file_cache[file_path] = ParsedFileInfo(
                    file_path=file_path,
                    ast_tree=None,
                    parse_error=str(e),
                )

        return self._file_cache[file_path]

    def validate_directory(
        self, directory: Path, verbose: bool = False
    ) -> list[tuple[str, str, str]]:
        """Validate all Python files in a directory."""
        results: list[tuple[str, str, str]] = []

        for file_path in self._get_all_python_files():
            try:
                file_path.relative_to(directory)
            except ValueError:
                continue

            message, severity = self.check_file_name(file_path)
            if message:
                results.append((str(file_path), message, severity))
            elif verbose:
                print(f"  OK: {file_path.name}")

        return results

    def validate_naming_conventions(self, verbose: bool = False) -> bool:
        """Validate all naming conventions."""
        file_results = self.validate_directory(self.repo_path, verbose)
        for file_path, message, severity in file_results:
            self.violations.append(
                NamingViolation(
                    file_path=file_path,
                    line_number=1,
                    class_name="(file name)",
                    expected_pattern="See directory prefix rules",
                    description=message,
                    severity=severity,
                )
            )

        for category, rules in self.NAMING_PATTERNS.items():
            self._validate_category(category, rules, verbose)

        return len([v for v in self.violations if v.severity == "error"]) == 0

    def _validate_category(
        self, category: str, rules: dict[str, str | None], verbose: bool = False
    ) -> None:
        """Validate naming conventions for a category."""
        file_prefix = rules.get("file_prefix")
        expected_dir = rules.get("directory")

        files_to_validate: set[Path] = set()

        for file_path in self._get_all_python_files():
            if file_path.name == "__init__.py":
                continue

            matches_prefix = file_prefix and file_path.name.startswith(file_prefix)

            matches_dir = False
            if expected_dir:
                try:
                    relative_path = file_path.relative_to(self.repo_path)
                    if relative_path.parts and relative_path.parts[0] == expected_dir:
                        matches_dir = True
                except ValueError:
                    pass

            if matches_prefix or matches_dir:
                files_to_validate.add(file_path)

        for file_path in files_to_validate:
            self._validate_class_names_in_file(file_path, category, rules, verbose)

    def _validate_class_names_in_file(
        self,
        file_path: Path,
        category: str,
        rules: dict[str, str | None],
        verbose: bool = False,
    ) -> None:
        """Validate class names in a file."""
        resolved_path = file_path if file_path.is_absolute() else file_path.resolve()

        validation_key = (resolved_path, category)
        if validation_key in self._validated_file_categories:
            return
        self._validated_file_categories.add(validation_key)

        file_info = self._get_parsed_file_info(resolved_path)

        if file_info.parse_error:
            if verbose:
                print(f"  Warning: Could not parse {resolved_path}: {file_info.parse_error}")
            return

        for class_name, line_number in file_info.class_defs:
            self._check_class_naming(
                resolved_path, class_name, line_number, category, rules
            )

    def _check_class_naming(
        self,
        file_path: Path,
        class_name: str,
        line_number: int,
        category: str,
        rules: dict[str, str | None],
    ) -> None:
        """Check if a class name follows conventions."""
        description = rules.get("description")

        compiled_pattern = self._COMPILED_NAMING_PATTERNS.get(category)
        if not compiled_pattern:
            return

        if self._is_exception_class(class_name):
            return

        if self._matches_architectural_exemption(class_name, file_path):
            return

        if self._matches_any_valid_pattern(class_name):
            return

        file_prefix = rules.get("file_prefix", "")
        expected_dir = rules.get("directory")

        in_relevant_file = file_prefix and file_path.name.startswith(file_prefix)
        in_relevant_dir = False
        if expected_dir:
            try:
                relative_path = file_path.relative_to(self.repo_path)
                in_relevant_dir = (
                    relative_path.parts and relative_path.parts[0] == expected_dir
                )
            except ValueError:
                pass

        if not in_relevant_file and not in_relevant_dir:
            return

        if not compiled_pattern.match(class_name):
            if self._should_match_pattern(class_name, category):
                self.violations.append(
                    NamingViolation(
                        file_path=str(file_path),
                        line_number=line_number,
                        class_name=class_name,
                        expected_pattern=compiled_pattern.pattern,
                        description=description
                        or f"Must follow {category} naming conventions",
                        severity="error",
                    )
                )

    def _is_exception_class(self, class_name: str) -> bool:
        return any(
            pattern.match(class_name) for pattern in self._COMPILED_EXCEPTION_PATTERNS
        )

    def _matches_architectural_exemption(
        self, class_name: str, file_path: Path
    ) -> bool:
        try:
            relative_path = file_path.relative_to(self.repo_path)
            path_parts = relative_path.parts
        except ValueError:
            path_parts = file_path.parts

        for directory, exempted_patterns in self.ARCHITECTURAL_EXEMPTIONS.items():
            dir_name = directory.rstrip("/")
            if dir_name not in path_parts:
                continue

            for pattern in exempted_patterns:
                if pattern.endswith("*"):
                    if class_name.startswith(pattern[:-1]):
                        return True
                elif pattern.startswith("*"):
                    if class_name.endswith(pattern[1:]):
                        return True
                elif class_name == pattern:
                    return True

        return False

    _CATEGORY_INDICATORS: ClassVar[dict[str, tuple[str, ...]]] = {
        "handlers": ("handler",),
        "models": ("model", "data", "schema"),
        "enums": ("enum", "status"),
        "protocols": ("protocol",),
        "registries": ("registry",),
    }

    def _should_match_pattern(self, class_name: str, category: str) -> bool:
        indicators = self._CATEGORY_INDICATORS.get(category, ())
        class_lower = class_name.lower()
        return any(indicator in class_lower for indicator in indicators)

    def _matches_any_valid_pattern(self, class_name: str) -> bool:
        for compiled_pattern in self._COMPILED_NAMING_PATTERNS.values():
            if compiled_pattern.match(class_name):
                return True
        return False

    def generate_report(self) -> str:
        """Generate naming convention report."""
        if not self.violations and not self._skipped_large_files:
            return "Naming: PASS - All naming conventions are compliant"

        errors = [v for v in self.violations if v.severity == "error"]
        warnings = [v for v in self.violations if v.severity == "warning"]

        report = "Naming Convention Validation Report\n"
        report += "=" * 50 + "\n\n"
        report += f"Summary: {len(errors)} errors, {len(warnings)} warnings\n\n"

        if errors:
            report += "NAMING ERRORS (Must Fix):\n"
            report += "-" * 40 + "\n"
            for v in errors:
                report += f"  {v.class_name} (Line {v.line_number})\n"
                report += f"    File: {v.file_path}\n"
                report += f"    Expected: {v.expected_pattern}\n"
                report += f"    Rule: {v.description}\n\n"

        if warnings:
            report += "NAMING WARNINGS (Should Fix):\n"
            report += "-" * 40 + "\n"
            for v in warnings:
                report += f"  {v.class_name} (Line {v.line_number})\n"
                report += f"    File: {v.file_path}\n"
                report += f"    Issue: {v.description}\n\n"

        return report


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate omniintelligence naming conventions"
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=None,
        help="Path to validate (default: auto-detect src/omniintelligence)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with error code if warnings are found",
    )

    args = parser.parse_args()

    if args.repo_path:
        repo_path = Path(args.repo_path).resolve()
    else:
        script_path = Path(__file__).resolve()
        repo_path = script_path.parent.parent.parent / "src" / "omniintelligence"

    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        return 1

    if args.verbose:
        print(f"Validating naming conventions in: {repo_path}")

    validator = IntelligenceNamingConventionValidator(repo_path)
    validator.validate_naming_conventions(args.verbose)

    errors = len([v for v in validator.violations if v.severity == "error"])
    warnings = len([v for v in validator.violations if v.severity == "warning"])

    has_failures = errors > 0 or (args.fail_on_warnings and warnings > 0)

    print(validator.generate_report())

    if not has_failures:
        print("Naming: PASS")
    else:
        print(f"Naming: FAIL ({errors} error(s), {warnings} warning(s))")

    return 0 if not has_failures else 1


if __name__ == "__main__":
    sys.exit(main())
