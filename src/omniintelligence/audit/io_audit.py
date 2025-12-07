"""I/O Audit implementation for ONEX node purity enforcement.

This module provides AST-based static analysis to detect I/O violations
in ONEX nodes, enforcing the "pure compute / no I/O" architectural invariant.

Forbidden patterns:
- net-client: Network/DB client imports
- env-access: Environment variable access
- file-io: File system operations
"""

from __future__ import annotations

import ast
import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Sequence


# =========================================================================
# Configuration
# =========================================================================

# Directories to audit for I/O violations
# These should contain only pure nodes with no direct I/O
IO_AUDIT_TARGETS: list[str] = [
    "src/omniintelligence/nodes",
    # Future: Add more directories as they adopt the purity constraint
    # "src/omnibase_core/nodes",
]

# Forbidden network/DB client imports (prefix match)
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "confluent_kafka",
        "qdrant_client",
        "neo4j",
        "asyncpg",
        "httpx",
        "aiofiles",
    }
)

# Forbidden pathlib I/O method names
PATHLIB_IO_METHODS: frozenset[str] = frozenset(
    {
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "open",
    }
)

# Forbidden logging handler classes
LOGGING_FILE_HANDLERS: frozenset[str] = frozenset(
    {
        "FileHandler",
        "RotatingFileHandler",
        "TimedRotatingFileHandler",
        "WatchedFileHandler",
    }
)


# =========================================================================
# Enums
# =========================================================================


class EnumIOAuditRule(Enum):
    """I/O audit rule identifiers.

    These are the canonical rule IDs used in error messages and pragmas.
    """

    NET_CLIENT = "net-client"
    ENV_ACCESS = "env-access"
    FILE_IO = "file-io"


# =========================================================================
# Models
# =========================================================================


@dataclass(frozen=True)
class ModelIOAuditViolation:
    """Represents a single I/O audit violation.

    Attributes:
        file: Path to the file containing the violation.
        line: Line number (1-indexed).
        column: Column number (0-indexed).
        rule: The rule that was violated.
        message: Human-readable description of the violation.
    """

    file: Path
    line: int
    column: int
    rule: EnumIOAuditRule
    message: str

    def __str__(self) -> str:
        """Format as file:line: rule: message."""
        return f"{self.file}:{self.line}: {self.rule.value}: {self.message}"


@dataclass
class ModelInlinePragma:
    """Represents a parsed inline pragma comment.

    Attributes:
        rule: The rule being whitelisted.
        scope: The scope of the pragma (e.g., "next-line").
        line: The line number where the pragma appears.
    """

    rule: EnumIOAuditRule
    scope: str
    line: int


@dataclass
class ModelWhitelistEntry:
    """A single whitelist entry for a file or pattern.

    Attributes:
        path: File path or glob pattern.
        reason: Documented reason for the exception.
        allowed_rules: List of rule IDs allowed for this file.
    """

    path: str
    reason: str
    allowed_rules: list[str] = field(default_factory=list)


@dataclass
class ModelWhitelistConfig:
    """Complete whitelist configuration.

    Attributes:
        files: List of whitelisted file entries.
        schema_version: Version of the whitelist schema.
    """

    files: list[ModelWhitelistEntry] = field(default_factory=list)
    schema_version: str = "1.0.0"


@dataclass
class ModelAuditResult:
    """Result of an audit run.

    Attributes:
        violations: List of violations found.
        files_scanned: Number of files scanned.
        is_clean: True if no violations were found.
    """

    violations: list[ModelIOAuditViolation]
    files_scanned: int

    @property
    def is_clean(self) -> bool:
        """Return True if no violations found."""
        return len(self.violations) == 0


# =========================================================================
# AST Visitor
# =========================================================================


class IOAuditVisitor(ast.NodeVisitor):
    """AST visitor that detects I/O violations in Python source files.

    This visitor walks the AST and collects violations of the I/O audit rules:
    - net-client: Forbidden import statements
    - env-access: os.environ, os.getenv, os.putenv usage
    - file-io: open(), pathlib I/O, logging file handlers
    """

    def __init__(
        self,
        file_path: Path,
        source_lines: list[str] | None = None,
        *,
        honor_inline_pragmas: bool = False,
    ) -> None:
        """Initialize the visitor.

        Args:
            file_path: Path to the file being analyzed.
            source_lines: Optional list of source lines for pragma parsing.
            honor_inline_pragmas: If True, inline pragmas whitelist violations.
                Only set to True for files that are in the YAML whitelist.
        """
        self.file_path = file_path
        self.source_lines = source_lines or []
        self.violations: list[ModelIOAuditViolation] = []
        self._honor_inline_pragmas = honor_inline_pragmas
        self._pragmas: dict[int, ModelInlinePragma] = {}
        self._imported_names: dict[str, str] = {}  # alias -> module

        # Parse inline pragmas from source (for potential use)
        self._parse_pragmas()

    def _parse_pragmas(self) -> None:
        """Parse inline pragmas from source lines."""
        for i, line in enumerate(self.source_lines, start=1):
            pragma = parse_inline_pragma(line)
            if pragma is not None:
                pragma = ModelInlinePragma(
                    rule=pragma.rule,
                    scope=pragma.scope,
                    line=i,
                )
                self._pragmas[i] = pragma

    def _is_whitelisted_by_pragma(self, line: int, rule: EnumIOAuditRule) -> bool:
        """Check if a line is whitelisted by an inline pragma.

        Args:
            line: The line number to check.
            rule: The rule to check.

        Returns:
            True if the line is whitelisted for this rule.
        """
        # Only honor pragmas if explicitly enabled (file must be in YAML whitelist)
        if not self._honor_inline_pragmas:
            return False

        # Check if previous line has a pragma for this line
        pragma = self._pragmas.get(line - 1)
        if pragma is not None and pragma.scope == "next-line" and pragma.rule == rule:
            return True
        return False

    def _add_violation(
        self,
        node: ast.AST,
        rule: EnumIOAuditRule,
        message: str,
    ) -> None:
        """Add a violation if not whitelisted by pragma.

        Args:
            node: The AST node where the violation occurred.
            rule: The rule that was violated.
            message: Description of the violation.
        """
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)

        # Check inline pragma whitelist
        if self._is_whitelisted_by_pragma(line, rule):
            return

        self.violations.append(
            ModelIOAuditViolation(
                file=self.file_path,
                line=line,
                column=col,
                rule=rule,
                message=message,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements for forbidden modules."""
        for alias in node.names:
            module = alias.name
            asname = alias.asname or alias.name

            # Track import for later reference
            self._imported_names[asname] = module

            # Check if module or any prefix is forbidden
            for forbidden in FORBIDDEN_IMPORTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    self._add_violation(
                        node,
                        EnumIOAuditRule.NET_CLIENT,
                        f"Forbidden import: {module}",
                    )
                    break

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from-import statements for forbidden modules."""
        module = node.module or ""

        # Track imports
        for alias in node.names:
            asname = alias.asname or alias.name
            self._imported_names[asname] = f"{module}.{alias.name}"

        # Check if module is forbidden
        for forbidden in FORBIDDEN_IMPORTS:
            if module == forbidden or module.startswith(f"{forbidden}."):
                self._add_violation(
                    node,
                    EnumIOAuditRule.NET_CLIENT,
                    f"Forbidden import: from {module}",
                )
                return

        # Check for logging file handlers
        if module in ("logging", "logging.handlers"):
            for alias in node.names:
                if alias.name in LOGGING_FILE_HANDLERS:
                    self._add_violation(
                        node,
                        EnumIOAuditRule.FILE_IO,
                        f"Forbidden import: {alias.name} from {module}",
                    )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for I/O violations."""
        self._check_call_for_open(node)
        self._check_call_for_env_access(node)
        self._check_call_for_pathlib_io(node)
        self._check_call_for_logging_handler(node)
        self.generic_visit(node)

    def _check_call_for_open(self, node: ast.Call) -> None:
        """Check for open() and io.open() calls."""
        func = node.func

        # Check for bare open() call
        if isinstance(func, ast.Name) and func.id == "open":
            self._add_violation(
                node,
                EnumIOAuditRule.FILE_IO,
                "Forbidden call: open()",
            )
            return

        # Check for io.open() call
        if isinstance(func, ast.Attribute):
            if func.attr == "open":
                # Could be io.open or path.open
                if isinstance(func.value, ast.Name):
                    if func.value.id == "io":
                        self._add_violation(
                            node,
                            EnumIOAuditRule.FILE_IO,
                            "Forbidden call: io.open()",
                        )

    def _check_call_for_env_access(self, node: ast.Call) -> None:
        """Check for os.getenv() and os.putenv() calls."""
        func = node.func

        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "os":
                if func.attr == "getenv":
                    self._add_violation(
                        node,
                        EnumIOAuditRule.ENV_ACCESS,
                        "Forbidden call: os.getenv()",
                    )
                elif func.attr == "putenv":
                    self._add_violation(
                        node,
                        EnumIOAuditRule.ENV_ACCESS,
                        "Forbidden call: os.putenv()",
                    )
            # Check for os.environ.get()
            elif isinstance(func.value, ast.Attribute):
                if (
                    isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "os"
                    and func.value.attr == "environ"
                    and func.attr == "get"
                ):
                    self._add_violation(
                        node,
                        EnumIOAuditRule.ENV_ACCESS,
                        "Forbidden call: os.environ.get()",
                    )

    def _check_call_for_pathlib_io(self, node: ast.Call) -> None:
        """Check for pathlib I/O method calls."""
        func = node.func

        if isinstance(func, ast.Attribute):
            if func.attr in PATHLIB_IO_METHODS:
                # This might be a Path method call
                self._add_violation(
                    node,
                    EnumIOAuditRule.FILE_IO,
                    f"Forbidden call: Path.{func.attr}()",
                )

    def _check_call_for_logging_handler(self, node: ast.Call) -> None:
        """Check for logging file handler instantiation."""
        func = node.func

        # Check for logging.FileHandler(...) or FileHandler(...)
        if isinstance(func, ast.Name) and func.id in LOGGING_FILE_HANDLERS:
            self._add_violation(
                node,
                EnumIOAuditRule.FILE_IO,
                f"Forbidden call: {func.id}()",
            )
        elif isinstance(func, ast.Attribute) and func.attr in LOGGING_FILE_HANDLERS:
            self._add_violation(
                node,
                EnumIOAuditRule.FILE_IO,
                f"Forbidden call: {func.attr}()",
            )

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Check for os.environ[...] access."""
        value = node.value

        if isinstance(value, ast.Attribute):
            if (
                isinstance(value.value, ast.Name)
                and value.value.id == "os"
                and value.attr == "environ"
            ):
                self._add_violation(
                    node,
                    EnumIOAuditRule.ENV_ACCESS,
                    "Forbidden access: os.environ[...]",
                )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Check for 'key in os.environ' patterns."""
        for comparator in node.comparators:
            if isinstance(comparator, ast.Attribute):
                if (
                    isinstance(comparator.value, ast.Name)
                    and comparator.value.id == "os"
                    and comparator.attr == "environ"
                ):
                    self._add_violation(
                        node,
                        EnumIOAuditRule.ENV_ACCESS,
                        "Forbidden access: 'in os.environ' check",
                    )
                    break

        self.generic_visit(node)


# =========================================================================
# Pragma Parsing
# =========================================================================

# Regex for inline pragma: # io-audit: ignore-next-line <rule>
PRAGMA_PATTERN = re.compile(
    r"#\s*io-audit:\s*ignore-next-line\s+(net-client|env-access|file-io)"
)


def parse_inline_pragma(line: str) -> ModelInlinePragma | None:
    """Parse an inline pragma comment.

    Args:
        line: A single line of source code.

    Returns:
        ModelInlinePragma if valid pragma found, None otherwise.
    """
    match = PRAGMA_PATTERN.search(line)
    if match is None:
        return None

    rule_str = match.group(1)

    # Map string to enum
    rule_map = {
        "net-client": EnumIOAuditRule.NET_CLIENT,
        "env-access": EnumIOAuditRule.ENV_ACCESS,
        "file-io": EnumIOAuditRule.FILE_IO,
    }

    rule = rule_map.get(rule_str)
    if rule is None:
        return None

    return ModelInlinePragma(
        rule=rule,
        scope="next-line",
        line=0,  # Will be set by caller
    )


# =========================================================================
# Whitelist Loading
# =========================================================================


def load_whitelist(path: Path) -> ModelWhitelistConfig:
    """Load whitelist configuration from a YAML file.

    Args:
        path: Path to the whitelist YAML file.

    Returns:
        Parsed whitelist configuration.

    Raises:
        FileNotFoundError: If the whitelist file doesn't exist.
    """
    if not path.exists():
        return ModelWhitelistConfig()

    with path.open() as f:
        data = yaml.safe_load(f) or {}

    files: list[ModelWhitelistEntry] = []
    for entry in data.get("files", []):
        files.append(
            ModelWhitelistEntry(
                path=entry.get("path", ""),
                reason=entry.get("reason", ""),
                allowed_rules=entry.get("allowed_rules", []),
            )
        )

    return ModelWhitelistConfig(
        files=files,
        schema_version=data.get("schema_version", "1.0.0"),
    )


def apply_whitelist(
    violations: list[ModelIOAuditViolation],
    whitelist: ModelWhitelistConfig,
    file_path: Path,
    source_lines: list[str] | None = None,
) -> list[ModelIOAuditViolation]:
    """Filter violations based on whitelist configuration.

    Inline pragmas are ONLY honored for files that appear in the YAML whitelist.
    This ensures the YAML whitelist is the source of truth.

    Args:
        violations: List of violations to filter.
        whitelist: Whitelist configuration.
        file_path: Path to the file being checked.
        source_lines: Source lines for inline pragma parsing (optional).

    Returns:
        List of violations not covered by whitelist.
    """
    if not violations:
        return violations

    # Convert file_path to string for matching
    file_str = str(file_path)

    # Find matching whitelist entries
    allowed_rules: set[str] = set()
    file_in_whitelist = False

    for entry in whitelist.files:
        # Check if file matches pattern
        if fnmatch.fnmatch(file_str, f"*{entry.path}") or fnmatch.fnmatch(
            file_str, entry.path
        ):
            file_in_whitelist = True
            allowed_rules.update(entry.allowed_rules)

    # If file not in whitelist, inline pragmas don't apply
    if not file_in_whitelist:
        return violations

    # Parse inline pragmas if source lines provided
    pragma_whitelist: dict[int, EnumIOAuditRule] = {}
    if source_lines:
        for i, line in enumerate(source_lines, start=1):
            pragma = parse_inline_pragma(line)
            if pragma is not None:
                # Pragma on line i applies to line i+1
                pragma_whitelist[i + 1] = pragma.rule

    # Filter out whitelisted violations
    remaining: list[ModelIOAuditViolation] = []
    for v in violations:
        # Check YAML rule whitelist
        if v.rule.value in allowed_rules:
            continue

        # Check inline pragma whitelist (only for files in YAML)
        if v.line in pragma_whitelist and pragma_whitelist[v.line] == v.rule:
            continue

        remaining.append(v)

    return remaining


# =========================================================================
# Main Audit Functions
# =========================================================================


def audit_file(file_path: Path) -> list[ModelIOAuditViolation]:
    """Audit a single Python file for I/O violations.

    Args:
        file_path: Path to the Python file to audit.

    Returns:
        List of violations found.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        SyntaxError: If the file has Python syntax errors.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    source = file_path.read_text()
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        # Re-raise with file context
        raise SyntaxError(f"Syntax error in {file_path}: {e}") from e

    visitor = IOAuditVisitor(file_path, source_lines)
    visitor.visit(tree)

    return visitor.violations


def audit_files(
    files: Sequence[Path],
) -> list[ModelIOAuditViolation]:
    """Audit multiple Python files for I/O violations.

    Args:
        files: Sequence of file paths to audit.

    Returns:
        Combined list of violations from all files.
    """
    all_violations: list[ModelIOAuditViolation] = []

    for file_path in files:
        violations = audit_file(file_path)
        all_violations.extend(violations)

    return all_violations


def discover_python_files(targets: Sequence[str]) -> list[Path]:
    """Discover Python files in the target directories.

    Args:
        targets: List of directory paths to scan.

    Returns:
        List of Python file paths found.
    """
    files: list[Path] = []

    for target in targets:
        target_path = Path(target)
        if target_path.exists() and target_path.is_dir():
            files.extend(target_path.rglob("*.py"))

    return sorted(files)


def run_audit(
    targets: Sequence[str] | None = None,
    whitelist_path: Path | None = None,
) -> ModelAuditResult:
    """Run the full I/O audit on target directories.

    Args:
        targets: List of directory paths to audit. Defaults to IO_AUDIT_TARGETS.
        whitelist_path: Path to whitelist YAML. Optional.

    Returns:
        Audit result with violations and metadata.
    """
    if targets is None:
        targets = IO_AUDIT_TARGETS

    # Discover files
    files = discover_python_files(targets)

    # Load whitelist
    whitelist = ModelWhitelistConfig()
    if whitelist_path is not None and whitelist_path.exists():
        whitelist = load_whitelist(whitelist_path)

    # Audit files and apply whitelist
    all_violations: list[ModelIOAuditViolation] = []

    for file_path in files:
        violations = audit_file(file_path)
        # Read source for inline pragma processing
        source_lines = file_path.read_text().splitlines()
        remaining = apply_whitelist(violations, whitelist, file_path, source_lines)
        all_violations.extend(remaining)

    return ModelAuditResult(
        violations=all_violations,
        files_scanned=len(files),
    )
