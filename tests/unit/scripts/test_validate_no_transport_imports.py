# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the transport import validator script.

Tests the AST-based validator that enforces ARCH-002:
Nodes never touch Kafka directly. Runtime owns all Kafka plumbing.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

# Import the module under test
from scripts.validate_no_transport_imports import (
    BANNED_MODULES,
    SKIP_DIRECTORIES,
    SKIP_DIRECTORY_SUFFIXES,
    FileProcessingError,
    TransportImportChecker,
    Violation,
    check_file,
    iter_python_files,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# BANNED_MODULES CONFIGURATION TESTS
# =============================================================================


class TestBannedModulesConfig:
    """Tests for BANNED_MODULES configuration."""

    def test_banned_modules_contains_kafka_clients(self) -> None:
        """Kafka clients are banned per ARCH-002."""
        assert "kafka" in BANNED_MODULES
        assert "aiokafka" in BANNED_MODULES
        assert "confluent_kafka" in BANNED_MODULES

    def test_banned_modules_contains_http_clients(self) -> None:
        """HTTP clients are banned (transport layer)."""
        assert "aiohttp" in BANNED_MODULES
        assert "httpx" in BANNED_MODULES
        assert "requests" in BANNED_MODULES

    def test_banned_modules_contains_database_clients(self) -> None:
        """Database clients are banned (I/O layer)."""
        assert "asyncpg" in BANNED_MODULES
        assert "psycopg2" in BANNED_MODULES
        assert "psycopg" in BANNED_MODULES

    def test_banned_modules_contains_redis(self) -> None:
        """Redis clients are banned."""
        assert "redis" in BANNED_MODULES
        assert "aioredis" in BANNED_MODULES

    def test_banned_modules_contains_grpc(self) -> None:
        """gRPC is banned."""
        assert "grpc" in BANNED_MODULES

    def test_banned_modules_is_frozenset(self) -> None:
        """BANNED_MODULES should be immutable."""
        assert isinstance(BANNED_MODULES, frozenset)


# =============================================================================
# SKIP_DIRECTORIES CONFIGURATION TESTS
# =============================================================================


class TestSkipDirectoriesConfig:
    """Tests for SKIP_DIRECTORIES and SKIP_DIRECTORY_SUFFIXES configuration."""

    def test_skip_directories_contains_pycache(self) -> None:
        """__pycache__ should be skipped."""
        assert "__pycache__" in SKIP_DIRECTORIES

    def test_skip_directories_contains_venv(self) -> None:
        """Virtual environment directories should be skipped."""
        assert ".venv" in SKIP_DIRECTORIES
        assert "venv" in SKIP_DIRECTORIES

    def test_skip_directories_contains_legacy(self) -> None:
        """Legacy directories should be skipped."""
        assert "_legacy" in SKIP_DIRECTORIES
        assert "migration_sources" in SKIP_DIRECTORIES

    def test_skip_directory_suffixes_contains_egg_info(self) -> None:
        """egg-info directories should be skipped via suffix matching."""
        assert ".egg-info" in SKIP_DIRECTORY_SUFFIXES

    def test_skip_directories_is_frozenset(self) -> None:
        """SKIP_DIRECTORIES should be immutable."""
        assert isinstance(SKIP_DIRECTORIES, frozenset)

    def test_skip_directory_suffixes_is_frozenset(self) -> None:
        """SKIP_DIRECTORY_SUFFIXES should be immutable."""
        assert isinstance(SKIP_DIRECTORY_SUFFIXES, frozenset)


# =============================================================================
# TransportImportChecker TESTS - TYPE_CHECKING DETECTION
# =============================================================================


class TestTypeCheckingDetection:
    """Tests for TYPE_CHECKING block detection."""

    def test_direct_type_checking_guard(self) -> None:
        """Detect `if TYPE_CHECKING:` guard."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp  # Should NOT be flagged
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 0

    def test_aliased_constant_type_checking(self) -> None:
        """Detect `if TC:` when `from typing import TYPE_CHECKING as TC`."""
        source = """
from typing import TYPE_CHECKING as TC

if TC:
    import aiohttp  # Should NOT be flagged
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 0

    def test_module_qualified_type_checking(self) -> None:
        """Detect `if typing.TYPE_CHECKING:` guard."""
        source = """
import typing

if typing.TYPE_CHECKING:
    import aiohttp  # Should NOT be flagged
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 0

    def test_aliased_module_type_checking(self) -> None:
        """Detect `if t.TYPE_CHECKING:` when `import typing as t`."""
        source = """
import typing as t

if t.TYPE_CHECKING:
    import aiohttp  # Should NOT be flagged
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 0

    def test_module_alias_not_valid_as_direct_name(self) -> None:
        """Verify `if t:` is NOT a TYPE_CHECKING guard even with `import typing as t`.

        Module aliases (from `import typing as t`) are only valid for attribute access
        like `if t.TYPE_CHECKING:`. They are NOT tracked as valid direct names because
        `_type_checking_module_aliases` is only checked in `_is_type_checking_guard()`
        for ast.Attribute nodes, not ast.Name nodes. This is intentional: while
        `t.TYPE_CHECKING` clearly references the typing module's constant, a bare `if t:`
        could be any truthy value.
        """
        source = """
import typing as t

if t:
    import aiohttp  # SHOULD be flagged - bare name is not a TYPE_CHECKING guard
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # This should flag the import because `if t:` is not a TYPE_CHECKING guard
        # Only attribute access like `if t.TYPE_CHECKING:` is recognized
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_else_block_of_type_checking_guard(self) -> None:
        """Imports in the `else` block of TYPE_CHECKING should be flagged.

        The else block runs at runtime (when TYPE_CHECKING is False),
        so banned imports there are violations.
        """
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp  # Should NOT be flagged (type-only)
else:
    import asyncpg  # SHOULD be flagged (runtime)
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # Only the else block import should be flagged
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "asyncpg"

    def test_elif_not_affected_by_type_checking_guard(self) -> None:
        """Imports in elif blocks after TYPE_CHECKING should be flagged.

        Only the immediate if body is guarded, not elif branches.
        """
        source = """
from typing import TYPE_CHECKING

some_condition = True

if TYPE_CHECKING:
    import aiohttp  # Should NOT be flagged
elif some_condition:
    import redis  # SHOULD be flagged (elif is runtime)
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # The elif import should be flagged
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "redis"

    def test_not_type_checking_pattern_flagged(self) -> None:
        """Imports in `if not TYPE_CHECKING:` should be flagged.

        This pattern runs at runtime (when TYPE_CHECKING is False),
        so banned imports there are violations.
        """
        source = """
from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    import aiohttp  # SHOULD be flagged (runtime)
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # The negated TYPE_CHECKING import should be flagged
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_type_checking_with_boolean_operator_flagged(self) -> None:
        """Imports in `if TYPE_CHECKING and condition:` should be flagged.

        Only pure `if TYPE_CHECKING:` is a valid guard.
        Boolean operators make the condition runtime-dependent.
        """
        source = """
from typing import TYPE_CHECKING

some_condition = True

if TYPE_CHECKING and some_condition:
    import aiohttp  # SHOULD be flagged (not a pure guard)
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # The compound condition import should be flagged
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"


# =============================================================================
# TransportImportChecker TESTS - RELATIVE IMPORTS
# =============================================================================


class TestRelativeImportHandling:
    """Tests for relative import handling (should NOT be flagged)."""

    def test_relative_import_not_flagged(self) -> None:
        """Relative imports with banned module names should NOT be flagged.

        `from .aiohttp import X` refers to a local module named 'aiohttp',
        not the external aiohttp package.
        """
        source = "from .aiohttp import ClientSession"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # Relative import should NOT be flagged
        assert len(checker.violations) == 0

    def test_relative_import_double_dot_not_flagged(self) -> None:
        """Parent-relative imports should NOT be flagged."""
        source = "from ..aiohttp import ClientSession"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # Relative import should NOT be flagged
        assert len(checker.violations) == 0

    def test_relative_import_no_module_not_flagged(self) -> None:
        """Relative imports without module name should NOT be flagged."""
        source = "from . import something"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # Relative import should NOT be flagged
        assert len(checker.violations) == 0

    def test_absolute_import_still_flagged(self) -> None:
        """Absolute imports of banned modules should still be flagged.

        This ensures the relative import fix didn't break absolute import detection.
        """
        source = "from aiohttp import ClientSession"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        # Absolute import SHOULD be flagged
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"


# =============================================================================
# TransportImportChecker TESTS - VIOLATION DETECTION
# =============================================================================


class TestViolationDetection:
    """Tests for banned import detection."""

    def test_detects_direct_import(self) -> None:
        """Detect `import aiohttp`."""
        source = "import aiohttp"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_detects_from_import(self) -> None:
        """Detect `from aiohttp import ClientSession`."""
        source = "from aiohttp import ClientSession"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_detects_dotted_import(self) -> None:
        """Detect `import aiohttp.client`."""
        source = "import aiohttp.client"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_detects_dotted_from_import(self) -> None:
        """Detect `from aiohttp.client import ClientSession`."""
        source = "from aiohttp.client import ClientSession"
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 1
        assert checker.violations[0].module_name == "aiohttp"

    def test_detects_multiple_violations(self) -> None:
        """Detect multiple banned imports."""
        source = """
import aiohttp
import asyncpg
from redis import Redis
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 3
        modules = {v.module_name for v in checker.violations}
        assert modules == {"aiohttp", "asyncpg", "redis"}

    def test_allows_safe_imports(self) -> None:
        """Allow imports that are not banned."""
        source = """
import os
import sys
from pathlib import Path
from typing import Any
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 0

    def test_captures_line_number(self) -> None:
        """Violations include correct line numbers."""
        source = """
# Comment line 1
import os  # line 3

import aiohttp  # line 5
"""
        checker = TransportImportChecker(source)
        tree = ast.parse(source)
        checker.visit(tree)
        assert len(checker.violations) == 1
        assert checker.violations[0].line_number == 5


# =============================================================================
# check_file TESTS - FILE PROCESSING
# =============================================================================


class TestCheckFile:
    """Tests for check_file function."""

    def test_detects_violation_in_file(self, temp_dir: Path) -> None:
        """check_file detects violations in a real file."""
        test_file = temp_dir / "test.py"
        test_file.write_text("import aiohttp\n")

        violations, errors = check_file(test_file)

        assert len(violations) == 1
        assert violations[0].module_name == "aiohttp"
        assert violations[0].file_path == test_file
        assert len(errors) == 0

    def test_handles_empty_file(self, temp_dir: Path) -> None:
        """check_file handles empty files gracefully."""
        test_file = temp_dir / "empty.py"
        test_file.write_text("")

        violations, errors = check_file(test_file)

        assert len(violations) == 0
        assert len(errors) == 0

    def test_handles_syntax_error(self, temp_dir: Path) -> None:
        """check_file returns error for invalid Python syntax."""
        test_file = temp_dir / "invalid.py"
        test_file.write_text("def broken(\n")  # Invalid syntax

        violations, errors = check_file(test_file)

        assert len(violations) == 0
        assert len(errors) == 1
        assert errors[0].error_type == "SyntaxError"

    def test_handles_nonexistent_file(self) -> None:
        """check_file returns error for missing file."""
        violations, errors = check_file(Path("/nonexistent/file.py"))

        assert len(violations) == 0
        assert len(errors) == 1
        assert errors[0].error_type == "OSError"

    def test_type_checking_import_allowed(self, temp_dir: Path) -> None:
        """check_file allows TYPE_CHECKING imports."""
        test_file = temp_dir / "typed.py"
        test_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp
""")

        violations, errors = check_file(test_file)

        assert len(violations) == 0
        assert len(errors) == 0


# =============================================================================
# iter_python_files TESTS - FILE TRAVERSAL
# =============================================================================


class TestIterPythonFiles:
    """Tests for iter_python_files function."""

    def test_finds_python_files(self, temp_dir: Path) -> None:
        """iter_python_files finds .py files."""
        (temp_dir / "test.py").write_text("# test")
        (temp_dir / "other.txt").write_text("# not python")

        files = list(iter_python_files(temp_dir, set()))

        assert len(files) == 1
        assert files[0].name == "test.py"

    def test_skips_pycache(self, temp_dir: Path) -> None:
        """iter_python_files skips __pycache__ directories."""
        pycache = temp_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("# cached")
        (temp_dir / "real.py").write_text("# real")

        files = list(iter_python_files(temp_dir, set()))

        assert len(files) == 1
        assert files[0].name == "real.py"

    def test_skips_egg_info_suffix(self, temp_dir: Path) -> None:
        """iter_python_files skips directories ending in .egg-info."""
        egg_dir = temp_dir / "mypackage.egg-info"
        egg_dir.mkdir()
        (egg_dir / "PKG-INFO.py").write_text("# egg info")
        (temp_dir / "real.py").write_text("# real")

        files = list(iter_python_files(temp_dir, set()))

        assert len(files) == 1
        assert files[0].name == "real.py"

    def test_respects_excludes(self, temp_dir: Path) -> None:
        """iter_python_files respects exclusion paths."""
        excluded = temp_dir / "excluded"
        excluded.mkdir()
        (excluded / "skip.py").write_text("# skip")
        (temp_dir / "include.py").write_text("# include")

        files = list(iter_python_files(temp_dir, {excluded}))

        assert len(files) == 1
        assert files[0].name == "include.py"

    def test_finds_nested_files(self, temp_dir: Path) -> None:
        """iter_python_files finds files in nested directories."""
        nested = temp_dir / "level1" / "level2"
        nested.mkdir(parents=True)
        (nested / "deep.py").write_text("# deep")
        (temp_dir / "shallow.py").write_text("# shallow")

        files = list(iter_python_files(temp_dir, set()))

        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"deep.py", "shallow.py"}

    def test_excludes_by_path_component_not_basename(self, temp_dir: Path) -> None:
        """Exclusion requires path component match, not just basename match.

        This tests that `--exclude dir1/foo.py` does NOT exclude `dir2/foo.py`.
        Basename-only matching would be overly broad and cause false negatives
        where banned imports go undetected.
        """
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "foo.py").write_text("# dir1/foo.py")
        (dir2 / "foo.py").write_text("# dir2/foo.py - should NOT be excluded")

        # Exclude only dir1/foo.py (or just "dir1")
        files = list(iter_python_files(temp_dir, {dir1}))

        # dir2/foo.py should NOT be excluded despite sharing basename
        assert len(files) == 1
        assert files[0].name == "foo.py"
        assert "dir2" in str(files[0])

    def test_excludes_by_exact_path_component_sequence(self, temp_dir: Path) -> None:
        """Exclusion matches exact path component sequences.

        exclude="tests" matches "src/tests/file.py" but NOT "src/tests_util/file.py"
        because 'tests_util' != 'tests'.
        """
        tests_dir = temp_dir / "src" / "tests"
        tests_util_dir = temp_dir / "src" / "tests_util"
        tests_dir.mkdir(parents=True)
        tests_util_dir.mkdir(parents=True)
        (tests_dir / "test_foo.py").write_text("# should be excluded")
        (tests_util_dir / "helper.py").write_text("# should NOT be excluded")

        # Exclude "tests" as a path component
        files = list(iter_python_files(temp_dir, {Path("tests")}))

        # Only tests_util/helper.py should remain
        assert len(files) == 1
        assert files[0].name == "helper.py"


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestViolationDataclass:
    """Tests for Violation dataclass."""

    def test_violation_str(self) -> None:
        """Violation __str__ formats correctly."""
        v = Violation(
            file_path=Path("/test/file.py"),
            line_number=42,
            module_name="aiohttp",
            import_statement="import aiohttp",
        )
        assert "file.py:42" in str(v)
        assert "aiohttp" in str(v)

    def test_violation_is_frozen(self) -> None:
        """Violation is immutable."""
        v = Violation(
            file_path=Path("/test/file.py"),
            line_number=42,
            module_name="aiohttp",
            import_statement="import aiohttp",
        )
        with pytest.raises(AttributeError):
            v.line_number = 100  # type: ignore[misc]


class TestFileProcessingErrorDataclass:
    """Tests for FileProcessingError dataclass."""

    def test_error_str(self) -> None:
        """FileProcessingError __str__ formats correctly."""
        e = FileProcessingError(
            file_path=Path("/test/file.py"),
            error_type="SyntaxError",
            error_message="Invalid syntax",
        )
        assert "file.py" in str(e)
        assert "SyntaxError" in str(e)

    def test_error_is_frozen(self) -> None:
        """FileProcessingError is immutable."""
        e = FileProcessingError(
            file_path=Path("/test/file.py"),
            error_type="SyntaxError",
            error_message="Invalid syntax",
        )
        with pytest.raises(AttributeError):
            e.error_type = "OSError"  # type: ignore[misc]
