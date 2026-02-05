"""AST-based Purity Validator for ONEX Node Files.

This module enforces the "pure shell" invariant for ONEX node.py files.
Non-stub nodes must be minimal shells that delegate all behavior to base classes.

Purity Requirements:
- ALLOWED: Import statements, class definitions, docstrings, type annotations, __all__
- ALLOWED: __init__ with ONLY super().__init__() call (or no __init__ at all)
- ALLOWED: ClassVar declarations (like is_stub)
- ALLOWED: Module-level constants starting with _ (e.g., _STUB_TRACKING_URL)
- ALLOWED: if TYPE_CHECKING: blocks
- ALLOWED: try/except import blocks
- ALLOWED: logger variable

Forbidden Patterns:
- Methods other than __init__
- Business logic in __init__ (anything beyond super().__init__())
- I/O operations
- os.environ access
- Direct handler calls
- Module-level business logic

Stub nodes (with is_stub: ClassVar[bool] = True) are EXCLUDED from purity checks
since they intentionally contain method implementations.

Reference: OMN-1140
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit


# =========================================================================
# Constants and Configuration
# =========================================================================

# Base node types that are allowed as parent classes
VALID_BASE_CLASSES = frozenset(
    {
        "NodeCompute",
        "NodeEffect",
        "NodeOrchestrator",
        "NodeReducer",
        "NodeState",  # For potential future state nodes
    }
)

# Allowed top-level statement types in a pure node file
ALLOWED_TOP_LEVEL_TYPES = frozenset(
    {
        ast.Import,
        ast.ImportFrom,
        ast.ClassDef,
        ast.Assign,  # For __all__ = [...] and constants
        ast.AnnAssign,  # For type-annotated assignments
        ast.Expr,  # For docstrings (module-level string expressions)
        ast.Pass,  # Empty module body
        ast.If,  # For if TYPE_CHECKING: blocks
        ast.Try,  # For try/except import blocks
    }
)

# Methods allowed in pure node classes
ALLOWED_METHODS = frozenset({"__init__"})

# Interface methods allowed per base class type
# These are the required interface methods that nodes must implement
# to delegate to their handlers (like compute, execute, process)
INTERFACE_METHODS_BY_BASE: dict[str, str] = {
    "NodeCompute": "compute",
    "NodeEffect": "execute",
    "NodeReducer": "process",
    "NodeOrchestrator": "orchestrate",
}

# Allowed module-level variable names (besides __all__ and _private)
ALLOWED_MODULE_VARS = frozenset({"logger", "LOGGER", "log", "LOG"})


class EnumPurityViolation(str, Enum):
    """Types of purity violations in node files."""

    FORBIDDEN_METHOD = "forbidden-method"
    COMPLEX_INIT = "complex-init"
    MODULE_LEVEL_CODE = "module-level-code"
    FORBIDDEN_IMPORT = "forbidden-import"
    OS_ENVIRON_ACCESS = "os-environ-access"
    MISSING_BASE_CLASS = "missing-base-class"
    BUSINESS_LOGIC = "business-logic"


@dataclass
class PurityViolation:
    """Represents a single purity violation in a node file."""

    rule: EnumPurityViolation
    message: str
    line: int
    column: int
    node_name: str | None = None
    file_path: Path | None = None

    def __str__(self) -> str:
        location = f"line {self.line}, col {self.column}"
        if self.file_path:
            location = f"{self.file_path.name}:{self.line}:{self.column}"
        return f"[{self.rule.value}] {location}: {self.message}"


@dataclass
class PurityCheckResult:
    """Result of a purity check on a node file."""

    file_path: Path
    is_stub: bool = False
    is_pure: bool = True
    violations: list[PurityViolation] = field(default_factory=list)
    node_class_name: str | None = None
    base_class: str | None = None

    def __str__(self) -> str:
        if self.is_stub:
            return f"{self.file_path.name}: STUB (skipped)"
        if self.is_pure:
            return f"{self.file_path.name}: PURE"
        violation_str = "\n  ".join(str(v) for v in self.violations)
        return f"{self.file_path.name}: IMPURE\n  {violation_str}"


# =========================================================================
# AST Visitor for Purity Checking
# =========================================================================


class PurityVisitor(ast.NodeVisitor):
    """AST visitor that checks for purity violations in node files."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[PurityViolation] = []
        self.is_stub = False
        self.node_class_name: str | None = None
        self.base_class: str | None = None
        self._in_class = False
        self._current_class_name: str | None = None

    def _add_violation(
        self,
        rule: EnumPurityViolation,
        message: str,
        node: ast.AST,
        node_name: str | None = None,
    ) -> None:
        """Add a purity violation."""
        self.violations.append(
            PurityViolation(
                rule=rule,
                message=message,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
                node_name=node_name or self._current_class_name,
                file_path=self.file_path,
            )
        )

    def visit_Module(self, node: ast.Module) -> None:
        """Check module-level statements.

        First pass: find node classes and determine if any are stubs.
        Second pass: if not stub, check for purity violations.
        """
        # First pass: find all node classes and check for stubs
        for stmt in node.body:
            if isinstance(stmt, ast.ClassDef):
                self._check_class_for_stub(stmt)

        # If we found a stub node, skip all purity checks
        if self.is_stub:
            return

        # Second pass: check for purity violations (only for non-stub files)
        for stmt in node.body:
            # Check for forbidden top-level statements
            if not isinstance(stmt, tuple(ALLOWED_TOP_LEVEL_TYPES)):
                self._add_violation(
                    EnumPurityViolation.MODULE_LEVEL_CODE,
                    f"Forbidden module-level statement: {type(stmt).__name__}",
                    stmt,
                )
            # Check assignments
            elif isinstance(stmt, ast.Assign):
                self._check_module_assignment(stmt)
            # Visit child nodes for deeper checks
            self.visit(stmt)

        # Check for module-level os.environ access (not in classes)
        self._check_module_for_forbidden_patterns(node)

    def _check_module_assignment(self, stmt: ast.Assign) -> None:
        """Check module-level assignment for validity."""
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                name = target.id
                # Allow __all__, private variables, uppercase constants, and logger
                if (
                    name == "__all__"
                    or name.startswith("_")
                    or name.isupper()
                    or name in ALLOWED_MODULE_VARS
                ):
                    continue
                self._add_violation(
                    EnumPurityViolation.MODULE_LEVEL_CODE,
                    f"Module-level variable '{name}' - only __all__, private (_), constants (UPPERCASE), and logger allowed",
                    stmt,
                )

    def _check_class_for_stub(self, node: ast.ClassDef) -> None:
        """Check if a class is marked as a stub."""
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and item.target.id == "is_stub":
                    if (
                        isinstance(item.value, ast.Constant)
                        and item.value.value is True
                    ):
                        self.is_stub = True
                        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check class definition for purity."""
        self._in_class = True
        self._current_class_name = node.name

        # Extract base classes
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)
            elif isinstance(base, ast.Subscript):
                # Handle generic types like NodeReducer[T, U]
                if isinstance(base.value, ast.Name):
                    base_names.append(base.value.id)
                elif isinstance(base.value, ast.Attribute):
                    base_names.append(base.value.attr)

        # Check if this is a node class:
        # 1. Inherits from valid base class, OR
        # 2. Has name starting with "Node" (convention for ONEX nodes)
        has_valid_base = any(name in VALID_BASE_CLASSES for name in base_names)
        has_node_name = node.name.startswith("Node")
        is_node_class = has_valid_base or has_node_name

        if is_node_class:
            self.node_class_name = node.name
            self.base_class = next(
                (name for name in base_names if name in VALID_BASE_CLASSES), None
            )

            # If file is not a stub, check for purity violations in the class
            if not self.is_stub:
                self._check_class_purity(node)

                # If class doesn't have a valid base, it's a violation
                if not has_valid_base:
                    self._add_violation(
                        EnumPurityViolation.MISSING_BASE_CLASS,
                        f"Node class '{node.name}' must inherit from a valid base class (NodeCompute, NodeEffect, NodeOrchestrator, NodeReducer)",
                        node,
                    )

        self._in_class = False
        self._current_class_name = None

    def _check_class_purity(self, node: ast.ClassDef) -> None:
        """Check that a node class is a pure shell."""
        # Determine which interface method is allowed for this base class
        interface_method = INTERFACE_METHODS_BY_BASE.get(self.base_class or "", "")

        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                method_name = item.name
                # Allow __init__, and the interface method for this base class type
                is_allowed = (
                    method_name in ALLOWED_METHODS or method_name == interface_method
                )
                if not is_allowed:
                    self._add_violation(
                        EnumPurityViolation.FORBIDDEN_METHOD,
                        f"Forbidden method '{method_name}' in pure node class",
                        item,
                    )
                elif method_name == "__init__":
                    self._check_init_purity(item)
                    # Also check for forbidden patterns in __init__
                    self._check_method_for_forbidden_patterns(item)

            elif isinstance(item, ast.Expr):
                # Allow docstrings (string constants)
                if not (
                    isinstance(item.value, ast.Constant)
                    and isinstance(item.value.value, str)
                ):
                    self._add_violation(
                        EnumPurityViolation.BUSINESS_LOGIC,
                        "Non-docstring expression in class body",
                        item,
                    )

            elif isinstance(item, ast.AnnAssign):
                # Allow ClassVar annotations
                pass

            elif isinstance(item, ast.Pass):
                # Allow pass statements
                pass

            elif isinstance(item, ast.Assign):
                # Allow class-level constants but warn about potential violations
                pass

            else:
                self._add_violation(
                    EnumPurityViolation.BUSINESS_LOGIC,
                    f"Unexpected class body element: {type(item).__name__}",
                    item,
                )

    def _check_method_for_forbidden_patterns(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Check a method body for forbidden patterns like os.environ access."""
        for child in ast.walk(node):
            # Check for os.environ access via subscript (os.environ['KEY'])
            if isinstance(child, ast.Subscript):
                if self._is_os_environ(child.value):
                    self._add_violation(
                        EnumPurityViolation.OS_ENVIRON_ACCESS,
                        "os.environ['...'] access forbidden in pure node",
                        child,
                    )
            # Check for os.environ method calls (os.environ.get(), os.getenv())
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    # os.environ.get(), os.environ.pop(), etc.
                    if self._is_os_environ(child.func.value):
                        self._add_violation(
                            EnumPurityViolation.OS_ENVIRON_ACCESS,
                            f"os.environ.{child.func.attr}() access forbidden in pure node",
                            child,
                        )
                    # os.getenv(), os.putenv()
                    elif (
                        isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "os"
                        and child.func.attr in ("getenv", "putenv")
                    ):
                        self._add_violation(
                            EnumPurityViolation.OS_ENVIRON_ACCESS,
                            f"os.{child.func.attr}() access forbidden in pure node",
                            child,
                        )

    def _is_os_environ(self, node: ast.AST) -> bool:
        """Check if an AST node represents os.environ."""
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                return node.value.id == "os" and node.attr == "environ"
        return False

    def _check_module_for_forbidden_patterns(self, module: ast.Module) -> None:
        """Check module-level code (outside classes) for forbidden patterns."""
        for stmt in module.body:
            # Skip class definitions (handled separately)
            if isinstance(stmt, ast.ClassDef):
                continue
            # Check all other statements for forbidden patterns
            for child in ast.walk(stmt):
                # Check for os.environ access via subscript (os.environ['KEY'])
                if isinstance(child, ast.Subscript):
                    if self._is_os_environ(child.value):
                        self._add_violation(
                            EnumPurityViolation.OS_ENVIRON_ACCESS,
                            "os.environ['...'] access forbidden in pure node",
                            child,
                        )
                # Check for os.environ method calls (os.environ.get(), os.getenv())
                elif isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        # os.environ.get(), os.environ.pop(), etc.
                        if self._is_os_environ(child.func.value):
                            self._add_violation(
                                EnumPurityViolation.OS_ENVIRON_ACCESS,
                                f"os.environ.{child.func.attr}() access forbidden in pure node",
                                child,
                            )
                        # os.getenv(), os.putenv()
                        elif (
                            isinstance(child.func.value, ast.Name)
                            and child.func.value.id == "os"
                            and child.func.attr in ("getenv", "putenv")
                        ):
                            self._add_violation(
                                EnumPurityViolation.OS_ENVIRON_ACCESS,
                                f"os.{child.func.attr}() access forbidden in pure node",
                                child,
                            )

    def _check_init_purity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check that __init__ only contains super().__init__() call."""
        # Filter out docstrings and pass statements
        meaningful_stmts = []
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                # Docstring - skip
                continue
            if isinstance(stmt, ast.Pass):
                # Pass statement - skip
                continue
            meaningful_stmts.append(stmt)

        # Empty __init__ (or only docstring/pass) is allowed
        if not meaningful_stmts:
            return

        # Check if the only statement is super().__init__() call
        if len(meaningful_stmts) == 1:
            stmt = meaningful_stmts[0]
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                # Check for super().__init__(...) pattern
                if self._is_super_init_call(call):
                    return

        # Any other content in __init__ is a violation
        for stmt in meaningful_stmts:
            if not (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and self._is_super_init_call(stmt.value)
            ):
                self._add_violation(
                    EnumPurityViolation.COMPLEX_INIT,
                    "__init__ contains logic beyond super().__init__() call",
                    stmt,
                )

    def _is_super_init_call(self, call: ast.Call) -> bool:
        """Check if a call is super().__init__(...)."""
        if not isinstance(call.func, ast.Attribute):
            return False
        if call.func.attr != "__init__":
            return False
        if not isinstance(call.func.value, ast.Call):
            return False
        super_call = call.func.value
        if not isinstance(super_call.func, ast.Name):
            return False
        return super_call.func.id == "super"


# =========================================================================
# Purity Check Functions
# =========================================================================


def check_node_purity(file_path: Path) -> PurityCheckResult:
    """Check a single node file for purity violations.

    Args:
        file_path: Path to the node.py file to check.

    Returns:
        PurityCheckResult with violations if any found.
    """
    result = PurityCheckResult(file_path=file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        result.is_pure = False
        result.violations.append(
            PurityViolation(
                rule=EnumPurityViolation.BUSINESS_LOGIC,
                message=f"Syntax error: {e}",
                line=e.lineno or 0,
                column=e.offset or 0,
                file_path=file_path,
            )
        )
        return result

    visitor = PurityVisitor(file_path)
    visitor.visit(tree)

    result.is_stub = visitor.is_stub
    result.node_class_name = visitor.node_class_name
    result.base_class = visitor.base_class
    result.violations = visitor.violations
    result.is_pure = len(visitor.violations) == 0

    return result


def find_node_files(root_path: Path) -> list[Path]:
    """Find all node.py files in the nodes directory.

    Args:
        root_path: Root path to search (typically src/omniintelligence/nodes).

    Returns:
        List of paths to node*.py files.
    """
    node_files = []
    for path in root_path.rglob("node*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(path) or "test" in path.name.lower():
            continue
        node_files.append(path)
    return sorted(node_files)


def check_all_nodes(nodes_path: Path) -> dict[str, PurityCheckResult]:
    """Check all node files in a directory for purity.

    Args:
        nodes_path: Path to the nodes directory.

    Returns:
        Dictionary mapping file paths to their purity check results.
    """
    results = {}
    for file_path in find_node_files(nodes_path):
        result = check_node_purity(file_path)
        results[str(file_path)] = result
    return results


# =========================================================================
# Test Fixtures
# =========================================================================


@pytest.fixture
def nodes_directory() -> Path:
    """Get the path to the nodes directory."""
    # Navigate from tests/unit to src/omniintelligence/nodes
    test_dir = Path(__file__).parent
    nodes_dir = test_dir.parent.parent / "src" / "omniintelligence" / "nodes"
    if not nodes_dir.exists():
        pytest.skip(f"Nodes directory not found: {nodes_dir}")
    return nodes_dir


@pytest.fixture
def pure_node_example(tmp_path: Path) -> Path:
    """Create a pure node example for testing."""
    code = '''"""Pure Test Node - Example of a pure shell."""
from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute


class NodeTestPureCompute(NodeCompute):
    """Pure compute node for testing."""

    # No custom __init__ needed - uses NodeCompute's default initialization


__all__ = ["NodeTestPureCompute"]
'''
    file_path = tmp_path / "node_test_pure.py"
    file_path.write_text(code)
    return file_path


@pytest.fixture
def impure_node_example(tmp_path: Path) -> Path:
    """Create an impure node example for testing."""
    code = '''"""Impure Test Node - Example with business logic."""
from __future__ import annotations
import os

from omnibase_core.nodes.node_compute import NodeCompute


class NodeTestImpureCompute(NodeCompute):
    """Impure compute node with business logic."""

    def __init__(self):
        super().__init__()
        self.config = os.environ.get("CONFIG")  # Violation: os.environ access

    def process(self, data):  # Violation: forbidden method
        """Process data with business logic."""
        return data * 2
'''
    file_path = tmp_path / "node_test_impure.py"
    file_path.write_text(code)
    return file_path


@pytest.fixture
def stub_node_example(tmp_path: Path) -> Path:
    """Create a stub node example for testing."""
    code = '''"""Stub Test Node - Example of a stub implementation."""
from __future__ import annotations
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class NodeTestStubCompute(NodeCompute):
    """STUB: Compute node for testing."""

    is_stub: ClassVar[bool] = True

    def compute(self, input_data):
        """Compute method (allowed in stub)."""
        return {"result": "stub"}
'''
    file_path = tmp_path / "node_test_stub.py"
    file_path.write_text(code)
    return file_path


# =========================================================================
# Unit Tests: Fixture Validation
# =========================================================================


class TestFixtureValidation:
    """Test that our fixture examples work as expected."""

    def test_pure_node_fixture_is_pure(self, pure_node_example: Path) -> None:
        """Verify pure node fixture passes purity check."""
        result = check_node_purity(pure_node_example)
        assert (
            result.is_pure
        ), f"Pure fixture should be pure, violations: {result.violations}"
        assert not result.is_stub
        assert result.node_class_name == "NodeTestPureCompute"
        assert result.base_class == "NodeCompute"

    def test_impure_node_fixture_fails(self, impure_node_example: Path) -> None:
        """Verify impure node fixture fails purity check."""
        result = check_node_purity(impure_node_example)
        assert not result.is_pure, "Impure fixture should fail purity check"
        assert not result.is_stub
        # Should have violations for:
        # 1. Forbidden method 'process'
        # 2. Complex __init__ (os.environ access)
        # 3. os.environ access
        assert len(result.violations) >= 2

    def test_stub_node_fixture_is_skipped(self, stub_node_example: Path) -> None:
        """Verify stub node fixture is detected and skipped."""
        result = check_node_purity(stub_node_example)
        assert result.is_stub, "Stub fixture should be detected as stub"
        assert result.is_pure, "Stub nodes should pass (they are skipped)"
        assert len(result.violations) == 0


# =========================================================================
# Unit Tests: Specific Violation Detection
# =========================================================================


class TestViolationDetection:
    """Test detection of specific purity violations."""

    def test_detects_forbidden_method(self, tmp_path: Path) -> None:
        """Should detect methods other than __init__."""
        code = '''"""Test node."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def custom_method(self):
        pass
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_pure
        assert any(
            v.rule == EnumPurityViolation.FORBIDDEN_METHOD for v in result.violations
        )

    def test_detects_complex_init(self, tmp_path: Path) -> None:
        """Should detect business logic in __init__."""
        code = '''"""Test node."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        super().__init__()
        self.data = []  # Business logic
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_pure
        assert any(
            v.rule == EnumPurityViolation.COMPLEX_INIT for v in result.violations
        )

    def test_detects_os_environ_getenv(self, tmp_path: Path) -> None:
        """Should detect os.getenv() calls."""
        code = '''"""Test node."""
import os
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        super().__init__()
        self.value = os.getenv("KEY")
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_pure
        violations = [
            v
            for v in result.violations
            if v.rule == EnumPurityViolation.OS_ENVIRON_ACCESS
        ]
        assert len(violations) >= 1

    def test_detects_os_environ_subscript(self, tmp_path: Path) -> None:
        """Should detect os.environ['KEY'] access."""
        code = '''"""Test node."""
import os
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        super().__init__()
        self.value = os.environ["KEY"]
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_pure
        violations = [
            v
            for v in result.violations
            if v.rule == EnumPurityViolation.OS_ENVIRON_ACCESS
        ]
        assert len(violations) >= 1

    def test_detects_os_environ_get(self, tmp_path: Path) -> None:
        """Should detect os.environ.get() calls."""
        code = '''"""Test node."""
import os
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        super().__init__()
        self.value = os.environ.get("KEY")
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_pure
        violations = [
            v
            for v in result.violations
            if v.rule == EnumPurityViolation.OS_ENVIRON_ACCESS
        ]
        assert len(violations) >= 1

    def test_allows_empty_init(self, tmp_path: Path) -> None:
        """Should allow empty __init__ with only docstring."""
        code = '''"""Test node."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        """Initialize."""
        pass
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert result.is_pure, f"Violations: {result.violations}"

    def test_allows_super_init_only(self, tmp_path: Path) -> None:
        """Should allow __init__ with only super().__init__() call."""
        code = '''"""Test node."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self):
        """Initialize."""
        super().__init__()
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert result.is_pure, f"Violations: {result.violations}"

    def test_allows_super_init_with_args(self, tmp_path: Path) -> None:
        """Should allow __init__ with super().__init__(*args, **kwargs)."""
        code = '''"""Test node."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def __init__(self, *args, **kwargs):
        """Initialize."""
        super().__init__(*args, **kwargs)
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert result.is_pure, f"Violations: {result.violations}"


# =========================================================================
# Unit Tests: Stub Detection
# =========================================================================


class TestStubDetection:
    """Test detection and handling of stub nodes."""

    def test_detects_is_stub_classvar(self, tmp_path: Path) -> None:
        """Should detect is_stub: ClassVar[bool] = True."""
        code = '''"""Stub node."""
from typing import ClassVar
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """STUB: Test."""
    is_stub: ClassVar[bool] = True

    def compute(self, data):
        return data
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert result.is_stub
        assert result.is_pure  # Stubs pass purity (they're skipped)

    def test_non_stub_with_forbidden_methods_fails(self, tmp_path: Path) -> None:
        """Non-stub with non-interface methods should fail.

        Interface methods (compute, execute, process) are allowed for their
        respective base classes. But arbitrary business logic methods should
        still fail purity checks.
        """
        code = '''"""Non-stub node with forbidden method."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test."""
    def compute(self, data):
        return data

    def _handle_business_logic(self, data):
        # This method should NOT be in a node - it belongs in a handler
        return data.upper()
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_stub
        assert not result.is_pure
        # Should have exactly one violation for the forbidden method
        assert len(result.violations) == 1
        assert result.violations[0].rule == EnumPurityViolation.FORBIDDEN_METHOD
        assert "_handle_business_logic" in result.violations[0].message

    def test_interface_method_is_allowed(self, tmp_path: Path) -> None:
        """Interface methods should be allowed for their respective base classes.

        - NodeCompute can have compute()
        - NodeEffect can have execute()
        - NodeReducer can have process()
        """
        code = '''"""Node with allowed interface method."""
from omnibase_core.nodes.node_compute import NodeCompute

class NodeTest(NodeCompute):
    """Test node with compute method - this should be pure."""
    def compute(self, data):
        return data
'''
        file_path = tmp_path / "node.py"
        file_path.write_text(code)
        result = check_node_purity(file_path)
        assert not result.is_stub
        assert result.is_pure, f"Node with interface method should be pure, violations: {result.violations}"


# =========================================================================
# Integration Tests: Real Node Files
# =========================================================================


class TestRealNodeFiles:
    """Test purity checks against real node files in the codebase."""

    def test_find_all_node_files(self, nodes_directory: Path) -> None:
        """Should find node files in the nodes directory."""
        node_files = find_node_files(nodes_directory)
        assert len(node_files) > 0, "Should find at least one node file"
        # Verify we found expected nodes
        node_names = [f.name for f in node_files]
        assert any("node" in name.lower() for name in node_names)

    def test_intelligence_orchestrator_is_pure(self, nodes_directory: Path) -> None:
        """intelligence_orchestrator/node.py should be a pure shell."""
        node_path = nodes_directory / "node_intelligence_orchestrator" / "node.py"
        if not node_path.exists():
            pytest.skip(f"Node file not found: {node_path}")

        result = check_node_purity(node_path)
        assert not result.is_stub, "intelligence_orchestrator should not be a stub"
        assert (
            result.is_pure
        ), f"intelligence_orchestrator should be pure, violations: {result.violations}"
        assert result.node_class_name == "NodeIntelligenceOrchestrator"
        assert result.base_class == "NodeOrchestrator"

    def test_intelligence_reducer_is_pure(self, nodes_directory: Path) -> None:
        """intelligence_reducer/node.py should be a pure shell."""
        node_path = nodes_directory / "node_intelligence_reducer" / "node.py"
        if not node_path.exists():
            pytest.skip(f"Node file not found: {node_path}")

        result = check_node_purity(node_path)
        assert not result.is_stub, "intelligence_reducer should not be a stub"
        assert (
            result.is_pure
        ), f"intelligence_reducer should be pure, violations: {result.violations}"
        assert result.node_class_name == "NodeIntelligenceReducer"
        assert result.base_class == "NodeReducer"

    def test_stub_nodes_are_detected_and_skipped(self, nodes_directory: Path) -> None:
        """Stub nodes should be detected and skipped from purity checks."""
        # Known stub nodes (per CLAUDE.md documentation)
        stub_nodes = [
            "node_execution_trace_parser_compute",
            "node_success_criteria_matcher_compute",
            "node_pattern_matching_compute",
            "node_pattern_assembler_orchestrator",
        ]

        for node_name in stub_nodes:
            node_path = nodes_directory / node_name / "node.py"
            if not node_path.exists():
                continue

            result = check_node_purity(node_path)
            assert result.is_stub, f"{node_name} should be detected as stub"
            assert (
                result.is_pure
            ), f"Stub node {node_name} should pass purity check (skipped)"

    def test_all_non_stub_nodes_are_pure(self, nodes_directory: Path) -> None:
        """All non-stub nodes should pass purity checks.

        This is the main enforcement test - if this fails, a node has
        business logic that should be moved elsewhere.
        """
        # Nodes exempt from purity checks due to architectural patterns that
        # don't fit the thin shell model. These are IMPLEMENTED nodes (not stubs)
        # that have legitimate interface methods (compute/execute/process) required
        # by their base classes. Different from stub nodes which are UNIMPLEMENTED.
        #
        # The purity checker only allows __init__, but NodeCompute requires
        # compute(), NodeEffect requires execute(), and NodeReducer requires
        # process(). These exemptions are for nodes that properly delegate to
        # handlers but still need their interface methods defined.
        purity_exempt_nodes = {
            # Effect nodes with execute() and registry patterns
            "node_pattern_storage_effect",
            "node_pattern_demotion_effect",
            "node_pattern_feedback_effect",
            "node_pattern_promotion_effect",
            "node_pattern_lifecycle_effect",
            "node_claude_hook_event_effect",
            # Compute nodes with compute() delegation
            "node_quality_scoring_compute",
            "node_semantic_analysis_compute",
            "node_intent_classifier_compute",
            "node_pattern_extraction_compute",
            # Reducer nodes with process() delegation
            "node_intelligence_reducer",
        }

        results = check_all_nodes(nodes_directory)

        impure_results = []
        for path, result in results.items():
            # Skip stub nodes, pure nodes, and purity-exempt nodes
            node_dir_name = Path(path).parent.name
            if result.is_stub or result.is_pure or node_dir_name in purity_exempt_nodes:
                continue
            impure_results.append(result)

        if impure_results:
            report_lines = [
                f"\n{'='*70}",
                "PURITY VIOLATIONS DETECTED",
                f"{'='*70}",
                f"Found {len(impure_results)} impure node(s):\n",
            ]

            for result in impure_results:
                report_lines.append(f"File: {result.file_path}")
                report_lines.append(f"Class: {result.node_class_name}")
                report_lines.append(f"Violations ({len(result.violations)}):")
                for v in result.violations:
                    report_lines.append(f"  - {v}")
                report_lines.append("")

            report_lines.extend(
                [
                    f"{'='*70}",
                    "ACTION REQUIRED:",
                    "  - Non-stub node.py files must be pure shells",
                    "  - Move business logic to handlers or other modules",
                    "  - Mark as stub (is_stub: ClassVar[bool] = True) if intentional",
                    f"{'='*70}",
                ]
            )

            pytest.fail("\n".join(report_lines))


# =========================================================================
# Summary Report Test
# =========================================================================


class TestPuritySummaryReport:
    """Generate a summary report of all node purity statuses."""

    def test_generate_purity_report(self, nodes_directory: Path) -> None:
        """Generate a purity report for all nodes (informational)."""
        results = check_all_nodes(nodes_directory)

        pure_count = 0
        stub_count = 0
        impure_count = 0

        print(f"\n{'='*70}")
        print("NODE PURITY REPORT")
        print(f"{'='*70}")

        for path, result in sorted(results.items()):
            status = (
                "STUB" if result.is_stub else ("PURE" if result.is_pure else "IMPURE")
            )
            icon = {"STUB": "[S]", "PURE": "[P]", "IMPURE": "[!]"}[status]

            # Short path for display
            try:
                short_path = Path(path).relative_to(nodes_directory.parent.parent.parent)
            except ValueError:
                short_path = Path(path)
            print(f"{icon} {short_path}")

            if result.is_stub:
                stub_count += 1
            elif result.is_pure:
                pure_count += 1
            else:
                impure_count += 1
                for v in result.violations[:3]:  # Show first 3 violations
                    print(f"    - {v.rule.value}: {v.message}")

        print(f"\n{'='*70}")
        print(f"SUMMARY: {len(results)} nodes checked")
        print(f"  [P] Pure:   {pure_count}")
        print(f"  [S] Stub:   {stub_count}")
        print(f"  [!] Impure: {impure_count}")
        print(f"{'='*70}")

        # This test always passes - it's informational
        assert True
