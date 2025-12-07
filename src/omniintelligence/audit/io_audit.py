"""I/O Audit implementation for ONEX node purity enforcement.

This module provides AST-based static analysis to detect I/O violations
in ONEX nodes, enforcing the "pure compute / no I/O" architectural invariant.

Forbidden patterns:
- net-client: Network/DB client imports
- env-access: Environment variable access
- file-io: File system operations

Whitelist Hierarchy
-------------------
The I/O audit uses a two-level whitelist system with a strict hierarchy:

1. **YAML Whitelist (Primary Source of Truth)**:
   - Located at ``tests/audit/io_audit_whitelist.yaml``
   - Defines which files are allowed exceptions and which rules apply
   - ALL exceptions MUST be registered here first

2. **Inline Pragmas (Secondary, Line-Level Granularity)**:
   - Format: ``# io-audit: ignore-next-line <rule>``
   - Provides fine-grained control within whitelisted files

**CRITICAL LIMITATION**: Inline pragmas ONLY work for files that are ALREADY
listed in the YAML whitelist. This is by design - the YAML whitelist is the
authoritative source of truth for which files may have I/O exceptions.

Example - Correct Usage
~~~~~~~~~~~~~~~~~~~~~~~
Step 1: Add file to YAML whitelist (io_audit_whitelist.yaml)::

    files:
      - path: "src/omniintelligence/nodes/my_effect_node.py"
        reason: "Effect node requires Kafka client for event publishing"
        allowed_rules:
          - "net-client"

Step 2: Use inline pragma for specific lines (my_effect_node.py)::

    # io-audit: ignore-next-line net-client
    from confluent_kafka import Producer  # Whitelisted by pragma

Example - INCORRECT Usage (pragma will be IGNORED)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If the file is NOT in the YAML whitelist, pragmas have no effect::

    # This pragma is IGNORED because file is not in YAML whitelist!
    # io-audit: ignore-next-line net-client
    from confluent_kafka import Producer  # VIOLATION REPORTED

Rationale
~~~~~~~~~
This design ensures:

- Central visibility of all I/O exceptions in one YAML file
- Code review coverage for any new exceptions (YAML changes are visible in PRs)
- Prevents developers from silently adding I/O to pure compute nodes
- Inline pragmas provide convenience without bypassing the approval process

Security Considerations for Whitelist Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The whitelist supports both exact file paths and glob patterns. However, overly
broad patterns can create security vulnerabilities by inadvertently whitelisting
more files than intended.

**Principle of Least Privilege**: Always use the most specific pattern possible.
Whitelist only the exact files that need exceptions, not entire directories.

**Dangerous Patterns (AVOID)**::

    # BAD: Whitelists ALL Python files - defeats the entire audit!
    - path: "**/*.py"
      allowed_rules: ["net-client"]

    # BAD: Whitelists entire directory - too broad
    - path: "src/omniintelligence/nodes/*"
      allowed_rules: ["env-access"]

    # BAD: Generic pattern matches too many files
    - path: "*_node.py"
      allowed_rules: ["file-io"]

**Safe Patterns (PREFERRED)**::

    # GOOD: Specific file path - clear intent, minimal scope
    - path: "src/omniintelligence/nodes/kafka_publisher/v1_0_0/node.py"
      reason: "Effect node requires Kafka client"
      allowed_rules: ["net-client"]

    # GOOD: Specific test fixtures - contained scope
    - path: "tests/audit/fixtures/io/whitelisted_node.py"
      reason: "Test fixture for whitelist functionality"
      allowed_rules: ["env-access"]

    # ACCEPTABLE: Limited glob for versioned nodes of same type
    - path: "src/omniintelligence/nodes/kafka_publisher/v*/node.py"
      reason: "All versions of Kafka publisher effect node"
      allowed_rules: ["net-client"]

**Pattern Security Guidelines**:

1. **Never use ``**/*.py``** - This effectively disables the audit
2. **Avoid bare wildcards** like ``*.py`` or ``*_node.py`` at the root
3. **Prefer full paths** over patterns when whitelisting single files
4. **Include version directories** in patterns for versioned nodes
5. **Always document the reason** - reviewers should understand why

The audit will emit warnings for patterns that appear overly permissive
(containing ``**/*`` or starting with ``*``).
"""

from __future__ import annotations

import ast
import logging
import re
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

import yaml

# Module logger for audit warnings
_logger = logging.getLogger(__name__)

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


# Default whitelist path (relative to repository root)
DEFAULT_WHITELIST_PATH: str = "tests/audit/io_audit_whitelist.yaml"

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

# Variable name patterns that strongly suggest a Path object.
# Used heuristically to detect likely Path I/O operations.
#
# NOTE: This includes short variable names like "p" and "fp" which are
# commonly used for Path objects. These may occasionally cause false positives
# if a non-Path object happens to have these names AND pathlib is imported
# in the same file. However, this trade-off is intentional:
#
#   - Most code that imports pathlib and uses "p" is actually using Path objects
#   - The pathlib import check (_has_pathlib_import) prevents false positives
#     in files that don't use pathlib at all
#   - True false positives can be resolved with inline pragmas or whitelist
#
# If false positives become problematic, consider removing "p" and "fp" and
# relying on the endswith("_path", "path") check in _is_likely_path_object.
PATHLIB_VARIABLE_PATTERNS: frozenset[str] = frozenset(
    {
        "path",
        "file_path",
        "filepath",
        "dir_path",
        "dirpath",
        "directory_path",
        "folder_path",
        "p",  # Common short name for Path - see NOTE above
        "fp",  # Common short name for file Path - see NOTE above
        "source_path",
        "target_path",
        "dest_path",
        "destination_path",
        "input_path",
        "output_path",
        "config_path",
        "log_path",
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

# os.environ mutation/access methods that indicate env variable access
# These are dict-like methods called on os.environ that read or mutate env vars
ENVIRON_MUTATION_METHODS: frozenset[str] = frozenset(
    {
        "get",
        "pop",
        "setdefault",
        "clear",
        "update",
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


# Valid rule IDs for whitelist validation
VALID_RULE_IDS: frozenset[str] = frozenset(r.value for r in EnumIOAuditRule)


# =========================================================================
# Remediation Hints and Suggestions
# =========================================================================

# Actionable guidance for each rule violation type.
# These hints follow ONEX architecture patterns (Effect nodes, DI).
REMEDIATION_HINTS: dict[EnumIOAuditRule, str] = {
    EnumIOAuditRule.NET_CLIENT: (
        "Move to an Effect node or inject client via dependency injection."
    ),
    EnumIOAuditRule.ENV_ACCESS: (
        "Pass configuration via constructor parameters instead of reading env vars."
    ),
    EnumIOAuditRule.FILE_IO: (
        "Move file I/O to an Effect node or pass file content as input parameter."
    ),
}


def _generate_suggestion(rule: EnumIOAuditRule, message: str) -> str:
    """Generate a context-specific remediation suggestion based on the violation.

    Analyzes the violation message to provide actionable code snippets or patterns
    that demonstrate the correct way to handle the I/O operation.

    Args:
        rule: The rule that was violated.
        message: The violation message containing context about the specific issue.

    Returns:
        A concrete suggestion with code example where applicable.
    """
    # Use match statement for exhaustive enum handling
    match rule:
        case EnumIOAuditRule.NET_CLIENT:
            return _generate_net_client_suggestion(message)
        case EnumIOAuditRule.ENV_ACCESS:
            return _generate_env_access_suggestion(message)
        case EnumIOAuditRule.FILE_IO:
            return _generate_file_io_suggestion(message)


def _generate_net_client_suggestion(message: str) -> str:
    """Generate suggestion for network/DB client violations."""
    # Extract the module/client name from the message
    msg_lower = message.lower()

    if "confluent_kafka" in msg_lower:
        return (
            "Create a separate Effect node for Kafka operations:\n"
            "  # node_kafka_publisher_effect.py\n"
            "  class NodeKafkaPublisherEffect:\n"
            "      def __init__(self, producer: Producer) -> None:\n"
            "          self._producer = producer  # Injected dependency"
        )
    elif "qdrant_client" in msg_lower:
        return (
            "Create a separate Effect node for Qdrant operations:\n"
            "  # node_vector_store_effect.py\n"
            "  class NodeVectorStoreEffect:\n"
            "      def __init__(self, client: QdrantClient) -> None:\n"
            "          self._client = client  # Injected dependency"
        )
    elif "httpx" in msg_lower:
        return (
            "Create a separate Effect node for HTTP operations:\n"
            "  # node_http_client_effect.py\n"
            "  class NodeHttpClientEffect:\n"
            "      def __init__(self, client: httpx.AsyncClient) -> None:\n"
            "          self._client = client  # Injected dependency"
        )
    elif "asyncpg" in msg_lower or "neo4j" in msg_lower:
        db_name = "PostgreSQL" if "asyncpg" in msg_lower else "Neo4j"
        return (
            f"Create a separate Effect node for {db_name} operations:\n"
            "  # node_database_effect.py\n"
            "  class NodeDatabaseEffect:\n"
            "      def __init__(self, connection: Connection) -> None:\n"
            "          self._conn = connection  # Injected dependency"
        )
    elif "aiofiles" in msg_lower:
        return (
            "Create a separate Effect node for async file operations:\n"
            "  # node_file_reader_effect.py\n"
            "  class NodeFileReaderEffect:\n"
            "      async def read_file(self, path: str) -> str:\n"
            "          async with aiofiles.open(path) as f:\n"
            "              return await f.read()"
        )

    # Generic suggestion for unknown clients
    return (
        "Create a separate Effect node and inject the client:\n"
        "  class NodeYourEffect:\n"
        "      def __init__(self, client: YourClient) -> None:\n"
        "          self._client = client  # Injected via DI"
    )


def _generate_env_access_suggestion(message: str) -> str:
    """Generate suggestion for environment variable access violations."""
    msg_lower = message.lower()

    # Try to extract the env var name if present
    # Pattern: os.getenv("FOO") or os.environ["FOO"] or os.environ.get("FOO")
    env_var_match = _ENV_VAR_PATTERN.search(message)

    if "getenv" in msg_lower or "environ" in msg_lower:
        if env_var_match:
            env_var = env_var_match.group(1)
            # Generate a config class name from the env var
            config_name = "".join(
                word.capitalize() for word in env_var.lower().split("_")
            )
            return (
                f"Inject configuration via constructor instead of reading {env_var}:\n"
                f"  from pydantic_settings import BaseSettings\n"
                f"\n"
                f"  class {config_name}Config(BaseSettings):\n"
                f"      {env_var.lower()}: str\n"
                f"\n"
                f"  class NodeYourCompute:\n"
                f"      def __init__(self, config: {config_name}Config) -> None:\n"
                f"          self._config = config  # Injected, not read from env"
            )

        # Generic env access suggestion
        return (
            "Inject configuration via constructor:\n"
            "  from pydantic_settings import BaseSettings\n"
            "\n"
            "  class YourConfig(BaseSettings):\n"
            "      your_setting: str\n"
            "\n"
            "  class NodeYourCompute:\n"
            "      def __init__(self, config: YourConfig) -> None:\n"
            "          self._config = config  # Injected, not read from env"
        )

    return "Pass configuration via constructor parameters instead of reading env vars."


def _generate_file_io_suggestion(message: str) -> str:
    """Generate suggestion for file I/O violations."""
    msg_lower = message.lower()

    if "open()" in msg_lower or "io.open()" in msg_lower:
        return (
            "Pass file content as a parameter instead of reading directly:\n"
            "  # Before (violation):\n"
            "  def process(self, file_path: str) -> Result:\n"
            "      with open(file_path) as f:\n"
            "          content = f.read()\n"
            "\n"
            "  # After (pure compute):\n"
            "  def process(self, content: str) -> Result:\n"
            "      # Content passed in, no I/O in compute node"
        )
    elif "read_text" in msg_lower or "read_bytes" in msg_lower:
        method = "read_text" if "read_text" in msg_lower else "read_bytes"
        return_type = "str" if method == "read_text" else "bytes"
        return (
            f"Pass file content as a parameter instead of using Path.{method}():\n"
            f"  # Before (violation):\n"
            f"  def process(self, path: Path) -> Result:\n"
            f"      content = path.{method}()\n"
            f"\n"
            f"  # After (pure compute):\n"
            f"  def process(self, content: {return_type}) -> Result:\n"
            f"      # Content passed in, no I/O in compute node"
        )
    elif "write_text" in msg_lower or "write_bytes" in msg_lower:
        return (
            "Return data to be written instead of writing directly:\n"
            "  # Before (violation):\n"
            "  def process(self, path: Path, data: str) -> None:\n"
            "      path.write_text(data)\n"
            "\n"
            "  # After (pure compute):\n"
            "  def process(self, data: str) -> str:\n"
            "      return processed_data  # Effect node handles writing"
        )
    elif "filehandler" in msg_lower:
        return (
            "Use structured logging without file handlers in compute nodes:\n"
            "  # Configure logging in Effect node or entry point, not in compute\n"
            "  # Compute nodes should use standard logging without file handlers:\n"
            "  import logging\n"
            "  logger = logging.getLogger(__name__)\n"
            "  logger.info('Message')  # Handler configured externally"
        )

    # Generic file I/O suggestion
    return (
        "Move file I/O to an Effect node or pass content as input:\n"
        "  class NodeFileReaderEffect:\n"
        "      def read(self, path: Path) -> str:\n"
        "          return path.read_text()\n"
        "\n"
        "  class NodeYourCompute:\n"
        "      def process(self, content: str) -> Result:\n"
        "          # Pure computation, no I/O"
    )


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
        suggestion: Context-specific remediation suggestion with code example.
    """

    file: Path
    line: int
    column: int
    rule: EnumIOAuditRule
    message: str
    suggestion: str = ""

    def __post_init__(self) -> None:
        """Generate suggestion if not provided."""
        if not self.suggestion:
            # Use object.__setattr__ since dataclass is frozen
            object.__setattr__(
                self, "suggestion", _generate_suggestion(self.rule, self.message)
            )

    def __str__(self) -> str:
        """Format as file:line: rule: message with remediation hint and suggestion."""
        base = f"{self.file}:{self.line}: {self.rule.value}: {self.message}"
        hint = REMEDIATION_HINTS.get(self.rule, "")
        lines = [base]
        if hint:
            lines.append(f"  -> Hint: {hint}")
        if self.suggestion:
            # Indent the suggestion for better readability
            suggestion_lines = self.suggestion.split("\n")
            lines.append("  -> Suggestion:")
            for sline in suggestion_lines:
                lines.append(f"     {sline}")
        return "\n".join(lines)


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
class ModelAuditMetrics:
    """Metrics about an audit run.

    Attributes:
        duration_ms: Time taken for the audit in milliseconds.
        violations_total: Total violations found before whitelisting.
        whitelisted_yaml_count: Violations whitelisted by YAML rules.
        whitelisted_pragma_count: Violations whitelisted by inline pragmas.
        violations_by_rule: Breakdown of total violations by rule type.
    """

    duration_ms: int = 0
    violations_total: int = 0
    whitelisted_yaml_count: int = 0
    whitelisted_pragma_count: int = 0
    violations_by_rule: dict[str, int] = field(default_factory=dict)


@dataclass
class ModelAuditResult:
    """Result of an audit run.

    Attributes:
        violations: List of violations found (after whitelisting).
        files_scanned: Number of files scanned.
        is_clean: True if no violations were found.
        metrics: Optional detailed metrics about the audit run.
    """

    violations: list[ModelIOAuditViolation]
    files_scanned: int
    metrics: ModelAuditMetrics | None = None

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
        self._check_call_for_forbidden_alias(node)
        self._check_call_for_open(node)
        self._check_call_for_env_access(node)
        self._check_call_for_pathlib_io(node)
        self._check_call_for_logging_handler(node)
        self.generic_visit(node)

    def _check_call_for_forbidden_alias(self, node: ast.Call) -> None:
        """Check for calls using aliased forbidden imports.

        Detects patterns like:
            import httpx as h
            h.get(url)  # Should be detected

            import confluent_kafka as ck
            ck.Producer({})  # Should be detected
        """
        func = node.func

        # Check for attribute access on a name (e.g., alias.method())
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                alias = func.value.id
                # Check if this alias maps to a forbidden module
                if alias in self._imported_names:
                    module = self._imported_names[alias]
                    for forbidden in FORBIDDEN_IMPORTS:
                        if module == forbidden or module.startswith(f"{forbidden}."):
                            self._add_violation(
                                node,
                                EnumIOAuditRule.NET_CLIENT,
                                f"Forbidden call via alias '{alias}': "
                                f"{alias}.{func.attr}() (import: {module})",
                            )
                            return

        # Check for direct call of an imported name (e.g., Producer())
        # This handles: from confluent_kafka import Producer as P; P({})
        if isinstance(func, ast.Name):
            alias = func.id
            if alias in self._imported_names:
                module = self._imported_names[alias]
                for forbidden in FORBIDDEN_IMPORTS:
                    if module.startswith(f"{forbidden}."):
                        self._add_violation(
                            node,
                            EnumIOAuditRule.NET_CLIENT,
                            f"Forbidden call via alias '{alias}': "
                            f"{alias}() (import: {module})",
                        )
                        return

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
        """Check for os.getenv(), os.putenv(), and os.environ mutation method calls."""
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
            # Check for os.environ method calls: get(), pop(), setdefault(), clear(), update()
            elif isinstance(func.value, ast.Attribute):
                if (
                    isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "os"
                    and func.value.attr == "environ"
                ):
                    if func.attr in ENVIRON_MUTATION_METHODS:
                        self._add_violation(
                            node,
                            EnumIOAuditRule.ENV_ACCESS,
                            f"Forbidden call: os.environ.{func.attr}()",
                        )

    def _is_likely_path_object(self, node: ast.expr) -> bool:
        """Check if an expression is likely a Path object.

        Uses heuristics based on:
        1. Whether pathlib or Path is imported in the file
        2. Variable naming patterns (e.g., "path", "file_path")
        3. Direct Path() constructor calls
        4. Chained method calls on Path-like expressions

        Args:
            node: The AST expression to check.

        Returns:
            True if the expression is likely a Path object.
        """
        # Check for Path() constructor call: Path(...).read_text()
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Path":
                return True
            # Check for pathlib.Path() call
            if isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "pathlib"
                    and node.func.attr == "Path"
                ):
                    return True

        # Check for variable with Path-like name
        if isinstance(node, ast.Name):
            var_name = node.id.lower()
            # Exact match with known patterns
            if var_name in PATHLIB_VARIABLE_PATTERNS:
                return True
            # Check for patterns like my_path, config_path, etc.
            if var_name.endswith(("_path", "path")):
                return True

        # Check for attribute access that might return a Path
        # e.g., self.path, config.file_path
        if isinstance(node, ast.Attribute):
            attr_name = node.attr.lower()
            if attr_name in PATHLIB_VARIABLE_PATTERNS:
                return True
            if attr_name.endswith(("_path", "path")):
                return True

        return False

    def _has_pathlib_import(self) -> bool:
        """Check if pathlib or Path is imported in this file.

        Returns:
            True if pathlib module or Path class is imported.
        """
        for alias, module in self._imported_names.items():
            # Check for: import pathlib, from pathlib import Path
            if module == "pathlib" or module.startswith("pathlib."):
                return True
            # Check for: from pathlib import Path (as something)
            if alias in {"Path", "pathlib"}:
                return True
        return False

    def _check_call_for_pathlib_io(self, node: ast.Call) -> None:
        """Check for pathlib I/O method calls.

        Only flags violations when:
        1. pathlib is imported in the file, AND
        2. The method is called on a likely Path object (based on heuristics)

        This reduces false positives for custom objects that happen to have
        methods with the same names (read_text, write_text, etc.).
        """
        func = node.func

        if isinstance(func, ast.Attribute):
            if func.attr in PATHLIB_IO_METHODS:
                # Only flag if pathlib is imported
                if not self._has_pathlib_import():
                    return

                # Only flag if the receiver looks like a Path object
                if not self._is_likely_path_object(func.value):
                    return

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

# Regex for extracting environment variable names from violation messages
# Matches: "FOO", 'FOO', "DATABASE_URL", etc.
_ENV_VAR_PATTERN = re.compile(r'["\']([A-Z_][A-Z0-9_]*)["\']')


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

    # Derive rule_map from enum to stay in sync automatically
    rule_map = {rule.value: rule for rule in EnumIOAuditRule}

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


def _validate_whitelist_entry(entry: ModelWhitelistEntry) -> None:
    """Validate a whitelist entry's allowed_rules and reason field.

    Args:
        entry: The whitelist entry to validate.

    Raises:
        ValueError: If any rule ID in allowed_rules is invalid,
            or if the reason field is empty or whitespace-only.
    """
    # Validate that reason is non-empty
    if not entry.reason or not entry.reason.strip():
        raise ValueError(
            f"Empty 'reason' field in whitelist entry for '{entry.path}'. "
            f"All whitelist entries must have a documented reason for the exception."
        )

    # Validate rule IDs
    for rule_id in entry.allowed_rules:
        if rule_id not in VALID_RULE_IDS:
            raise ValueError(
                f"Invalid rule ID '{rule_id}' in whitelist entry for '{entry.path}'. "
                f"Valid rule IDs are: {sorted(VALID_RULE_IDS)}"
            )


def load_whitelist(path: Path) -> ModelWhitelistConfig:
    """Load whitelist configuration from a YAML file.

    Args:
        path: Path to the whitelist YAML file.

    Returns:
        Parsed whitelist configuration. Returns an empty ModelWhitelistConfig
        if the file does not exist.

    Raises:
        ValueError: If the YAML file is malformed, or if any whitelist entry
            has an invalid rule ID or empty reason.
    """
    if not path.exists():
        return ModelWhitelistConfig()

    with path.open() as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in whitelist file '{path}': {e}") from e

    files: list[ModelWhitelistEntry] = []
    for entry in data.get("files", []):
        whitelist_entry = ModelWhitelistEntry(
            path=entry.get("path", ""),
            reason=entry.get("reason", ""),
            allowed_rules=entry.get("allowed_rules", []),
        )
        # Validate rule IDs before adding
        _validate_whitelist_entry(whitelist_entry)
        # Check for overly permissive patterns (security warning)
        _warn_overly_permissive_pattern(whitelist_entry)
        files.append(whitelist_entry)

    return ModelWhitelistConfig(
        files=files,
        schema_version=data.get("schema_version", "1.0.0"),
    )


def _is_glob_pattern(pattern: str) -> bool:
    """Check if a pattern contains glob wildcards.

    Args:
        pattern: The pattern to check.

    Returns:
        True if pattern contains * or ? glob characters.
    """
    return "*" in pattern or "?" in pattern


# Patterns that are considered overly permissive (security risk)
# These patterns match too many files and effectively bypass the audit
_OVERLY_PERMISSIVE_PATTERNS: tuple[str, ...] = (
    "**/*",  # Matches everything recursively
    "**/*.py",  # Matches all Python files
    "*.py",  # Matches all Python files in root
)


def _check_pattern_security(pattern: str) -> str | None:
    """Check if a whitelist pattern is overly permissive.

    Overly permissive patterns can create security vulnerabilities by
    inadvertently whitelisting more files than intended.

    Args:
        pattern: The whitelist path pattern to check.

    Returns:
        Warning message if pattern is overly permissive, None otherwise.

    Security Rules Checked:
        1. Exact match with dangerous patterns (``**/*``, ``**/*.py``, ``*.py``)
        2. Pattern starts with ``*`` (matches any file at root)
        3. Pattern contains ``**/*`` substring (recursive wildcard)
        4. Pattern is just a bare extension (``*.py``, ``*.yaml``)
    """
    # Normalize pattern for comparison
    normalized = pattern.strip()

    # Rule 1: Exact match with known dangerous patterns
    if normalized in _OVERLY_PERMISSIVE_PATTERNS:
        return (
            f"Pattern '{pattern}' matches ALL files of that type. "
            f"This effectively disables the I/O audit for those files."
        )

    # Rule 2: Pattern starts with bare wildcard (no directory prefix)
    if normalized.startswith("*") and "/" not in normalized:
        return (
            f"Pattern '{pattern}' starts with wildcard without directory prefix. "
            f"This matches files in any directory. Use a more specific path."
        )

    # Rule 3: Pattern contains recursive wildcard that's too broad
    # **/* at the start means "everything recursively"
    if normalized.startswith("**/"):
        # Check if it's just a bare extension pattern
        rest = normalized[3:]  # Remove **/
        if rest.startswith("*"):
            return (
                f"Pattern '{pattern}' is overly broad. "
                f"Consider using a more specific directory prefix."
            )

    return None


def _warn_overly_permissive_pattern(entry: ModelWhitelistEntry) -> None:
    """Emit a warning if a whitelist entry has an overly permissive pattern.

    This function checks the pattern and emits both a Python warning (for
    programmatic use) and a log warning (for CLI output).

    Args:
        entry: The whitelist entry to check.
    """
    warning_msg = _check_pattern_security(entry.path)
    if warning_msg:
        full_msg = (
            f"SECURITY WARNING: Overly permissive whitelist pattern detected. "
            f"{warning_msg} "
            f"Entry reason: '{entry.reason}'"
        )
        # Emit both warning types for maximum visibility
        warnings.warn(full_msg, UserWarning, stacklevel=3)
        _logger.warning(full_msg)


def _matches_whitelist_entry(file_str: str, file_path: Path, entry_path: str) -> bool:
    """Check if a file matches a whitelist entry.

    Matching rules:
        - If entry_path is a glob pattern (contains * or ?), use Path.match()
          which properly supports ** for recursive directory matching
        - If entry_path is a specific file, match exactly by:
          - Full path equality
          - File name equality (basename only)
          - Path suffix matching (for relative paths)

    Args:
        file_str: String representation of the file path.
        file_path: Path object of the file.
        entry_path: The whitelist entry path or pattern.

    Returns:
        True if the file matches the whitelist entry.

    Security Considerations:
        This function uses exact matching for non-glob patterns to prevent
        security vulnerabilities where a whitelist entry like "bad_node.py"
        would incorrectly match "my_bad_node.py" or "bad_node.py.backup".
        Substring or partial matching would allow attackers to bypass I/O
        restrictions by naming files to include whitelisted file names as
        substrings.

    Examples:
        Non-glob patterns (exact matching):
            - Entry "node.py" matches: "node.py", "src/nodes/node.py"
            - Entry "node.py" does NOT match: "my_node.py", "node.py.bak"
            - Entry "src/effect.py" matches: "project/src/effect.py"
            - Entry "src/effect.py" does NOT match: "other_src/effect.py"

        Glob patterns (wildcard matching):
            - Entry "*.py" matches: "foo.py", "bar.py"
            - Entry "**/test_*.py" matches: "a/b/test_foo.py", "test_bar.py"
            - Entry "nodes/*.py" matches: "nodes/effect.py", "src/nodes/compute.py"
    """
    if _is_glob_pattern(entry_path):
        # For glob patterns, use Path.match() which supports ** recursive matching
        # Try the pattern as-is, and also try with leading **/ for flexibility
        return file_path.match(entry_path) or file_path.match(f"**/{entry_path}")
    else:
        # For specific files, require exact match
        # Match either the full path or just the file name
        file_name = file_path.name
        entry_name = Path(entry_path).name

        # Exact full path match
        if file_str == entry_path:
            return True

        # Exact file name match (for convenience when specifying just filenames)
        if file_name == entry_name and entry_name == entry_path:
            return True

        # Path ends with the entry (for relative paths like "nodes/whitelisted_node.py")
        if file_str.endswith((f"/{entry_path}", f"\\{entry_path}")):
            return True

        return False


@dataclass
class ModelWhitelistStats:
    """Statistics about whitelist application for a file.

    Attributes:
        remaining: Violations remaining after whitelisting.
        yaml_count: Number of violations whitelisted by YAML rules.
        pragma_count: Number of violations whitelisted by inline pragmas.
    """

    remaining: list[ModelIOAuditViolation]
    yaml_count: int = 0
    pragma_count: int = 0


def apply_whitelist(
    violations: list[ModelIOAuditViolation],
    whitelist: ModelWhitelistConfig,
    file_path: Path,
    source_lines: list[str] | None = None,
    *,
    return_stats: bool = False,
) -> list[ModelIOAuditViolation] | ModelWhitelistStats:
    """Filter violations based on whitelist configuration.

    Inline pragmas are ONLY honored for files that appear in the YAML whitelist.
    This ensures the YAML whitelist is the source of truth.

    Args:
        violations: List of violations to filter.
        whitelist: Whitelist configuration.
        file_path: Path to the file being checked.
        source_lines: Source lines for inline pragma parsing (optional).
        return_stats: If True, return ModelWhitelistStats with counts.

    Returns:
        List of violations not covered by whitelist, or ModelWhitelistStats
        if return_stats is True.
    """
    if not violations:
        if return_stats:
            return ModelWhitelistStats(remaining=[])
        return violations

    # Convert file_path to string for matching
    file_str = str(file_path)

    # Find matching whitelist entries
    allowed_rules: set[str] = set()
    file_in_whitelist = False

    for entry in whitelist.files:
        # Check if file matches pattern using secure matching
        if _matches_whitelist_entry(file_str, file_path, entry.path):
            file_in_whitelist = True
            allowed_rules.update(entry.allowed_rules)

    # If file not in whitelist, inline pragmas don't apply
    if not file_in_whitelist:
        if return_stats:
            return ModelWhitelistStats(remaining=violations)
        return violations

    # Parse inline pragmas if source lines provided
    pragma_whitelist: dict[int, EnumIOAuditRule] = {}
    if source_lines:
        for i, line in enumerate(source_lines, start=1):
            pragma = parse_inline_pragma(line)
            if pragma is not None:
                # Pragma on line i applies to line i+1
                pragma_whitelist[i + 1] = pragma.rule

    # Filter out whitelisted violations, tracking counts
    remaining: list[ModelIOAuditViolation] = []
    yaml_count = 0
    pragma_count = 0

    for v in violations:
        # Check YAML rule whitelist
        if v.rule.value in allowed_rules:
            yaml_count += 1
            continue

        # Check inline pragma whitelist (only for files in YAML)
        if v.line in pragma_whitelist and pragma_whitelist[v.line] == v.rule:
            pragma_count += 1
            continue

        remaining.append(v)

    if return_stats:
        return ModelWhitelistStats(
            remaining=remaining,
            yaml_count=yaml_count,
            pragma_count=pragma_count,
        )
    return remaining


# =========================================================================
# Main Audit Functions
# =========================================================================


@overload
def audit_file(
    file_path: Path,
    *,
    return_source_lines: Literal[False] = False,
) -> list[ModelIOAuditViolation]: ...


@overload
def audit_file(
    file_path: Path,
    *,
    return_source_lines: Literal[True],
) -> tuple[list[ModelIOAuditViolation], list[str]]: ...


def audit_file(
    file_path: Path,
    *,
    return_source_lines: bool = False,
) -> list[ModelIOAuditViolation] | tuple[list[ModelIOAuditViolation], list[str]]:
    """Audit a single Python file for I/O violations.

    Args:
        file_path: Path to the Python file to audit.
        return_source_lines: If True, return a tuple of (violations, source_lines).
            This avoids redundant file reads when source lines are needed later.
            Defaults to False for backward compatibility.

    Returns:
        List of violations found if return_source_lines is False.
        Tuple of (violations, source_lines) if return_source_lines is True.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        SyntaxError: If the file has Python syntax errors.
        UnicodeDecodeError: If the file contains non-UTF8 characters.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"File '{file_path}' contains non-UTF8 characters. "
            f"Please ensure the file is saved with UTF-8 encoding.",
        ) from e
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        # Re-raise with file context
        raise SyntaxError(f"Syntax error in {file_path}: {e}") from e

    visitor = IOAuditVisitor(file_path, source_lines)
    visitor.visit(tree)

    if return_source_lines:
        return visitor.violations, source_lines
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

    This function recursively scans the specified directories for Python files
    (*.py) and returns a deduplicated, sorted list of canonical file paths.

    Symlink Handling
    ----------------
    The function handles symlinks as follows:

    - **File symlinks**: Resolved to canonical paths for deduplication. If the
      same file is reachable via multiple paths (direct + symlink), it appears
      only once in the result.

    - **Directory symlinks**: NOT followed by rglob() for security. If you need
      to audit files in a symlinked directory, add it to targets directly.

    - **Broken symlinks**: Skipped gracefully. When resolve() returns a path
      that doesn't exist (is_file() returns False), the symlink is ignored.

    - **Circular symlinks**: Skipped gracefully. When resolve() raises OSError
      (e.g., for self-referencing symlinks), the symlink is ignored.

    This behavior prevents:
    - Infinite loops from circular symlinks
    - Duplicate processing of files accessible via multiple paths
    - Crashes from broken symlinks in the target directories

    Args:
        targets: List of directory paths to scan.

    Returns:
        List of Python file paths found, deduplicated by canonical path
        and sorted alphabetically.

    Example:
        >>> files = discover_python_files(["src/nodes", "src/effects"])
        >>> for f in files:
        ...     violations = audit_file(f)
    """
    files: set[Path] = set()  # Use set for deduplication

    for target in targets:
        target_path = Path(target)
        if target_path.exists() and target_path.is_dir():
            for py_file in target_path.rglob("*.py"):
                # Resolve to canonical path for deduplication
                try:
                    canonical = py_file.resolve()
                    if canonical.is_file():  # Skip broken symlinks
                        files.add(canonical)
                except (OSError, RuntimeError):
                    # OSError: General file system errors
                    # RuntimeError: Python 3.12+ raises this for symlink loops
                    # Skip files that can't be resolved (circular symlinks, etc.)
                    pass

    return sorted(files)


def run_audit(
    targets: Sequence[str] | None = None,
    whitelist_path: Path | None = None,
    *,
    collect_metrics: bool = False,
) -> ModelAuditResult:
    """Run the full I/O audit on target directories.

    Args:
        targets: List of directory paths to audit. Defaults to IO_AUDIT_TARGETS.
        whitelist_path: Path to whitelist YAML. Optional.
        collect_metrics: If True, collect detailed metrics about the audit run.

    Returns:
        Audit result with violations and metadata. If collect_metrics is True,
        includes a ModelAuditMetrics object with detailed statistics.
    """
    start_time = time.perf_counter() if collect_metrics else 0

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

    # Metrics tracking (only when collecting)
    total_violations = 0
    total_yaml_whitelisted = 0
    total_pragma_whitelisted = 0
    violations_by_rule: dict[str, int] = {}

    for file_path in files:
        # Get violations and source_lines in single read (avoids redundant file read)
        violations, source_lines = audit_file(file_path, return_source_lines=True)

        if collect_metrics:
            # Count violations by rule before whitelisting
            total_violations += len(violations)
            for v in violations:
                rule_key = v.rule.value
                violations_by_rule[rule_key] = violations_by_rule.get(rule_key, 0) + 1

            # Get whitelist stats
            stats = apply_whitelist(
                violations, whitelist, file_path, source_lines, return_stats=True
            )
            # Type guard: stats is ModelWhitelistStats when return_stats=True
            assert isinstance(stats, ModelWhitelistStats)
            all_violations.extend(stats.remaining)
            total_yaml_whitelisted += stats.yaml_count
            total_pragma_whitelisted += stats.pragma_count
        else:
            # Fast path without metrics
            remaining = apply_whitelist(violations, whitelist, file_path, source_lines)
            # Type guard: remaining is list when return_stats=False
            assert isinstance(remaining, list)
            all_violations.extend(remaining)

    # Build metrics if requested
    metrics = None
    if collect_metrics:
        end_time = time.perf_counter()
        duration_ms = int((end_time - start_time) * 1000)
        metrics = ModelAuditMetrics(
            duration_ms=duration_ms,
            violations_total=total_violations,
            whitelisted_yaml_count=total_yaml_whitelisted,
            whitelisted_pragma_count=total_pragma_whitelisted,
            violations_by_rule=violations_by_rule,
        )

    return ModelAuditResult(
        violations=all_violations,
        files_scanned=len(files),
        metrics=metrics,
    )


# =========================================================================
# CLI Entry Point
# =========================================================================


if __name__ == "__main__":
    # Allow running as: python -m omniintelligence.audit.io_audit
    # Delegates to the main CLI in __main__.py
    import sys

    from omniintelligence.audit.__main__ import main

    sys.exit(main())
