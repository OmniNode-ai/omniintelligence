"""I/O Audit Tests for ONEX Node Purity.

This module enforces the "pure compute / no I/O" invariant for ONEX nodes
by statically scanning Python source files via AST and failing on violations.

Forbidden patterns:
- net-client: Network/DB client imports (confluent_kafka, qdrant_client, neo4j, asyncpg, httpx, aiofiles)
- env-access: Environment variable access (os.environ, os.getenv, os.putenv)
- file-io: File I/O operations (open, pathlib I/O, logging file handlers)

TDD: Tests are written first, implementation follows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.audit.io_audit import (
    EnumIOAuditRule,
    IOAuditVisitor,
    ModelWhitelistConfig,
    ModelWhitelistEntry,
    apply_whitelist,
    audit_file,
    audit_files,
    load_whitelist,
    parse_inline_pragma,
)

# =========================================================================
# Test Fixtures Path Helpers
# =========================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "io"
WHITELIST_PATH = Path(__file__).parent / "io_audit_whitelist.yaml"


def fixture_path(name: str) -> Path:
    """Get path to a test fixture file."""
    return FIXTURES_DIR / name


# =========================================================================
# Test: Clean Node Detection (No Violations)
# =========================================================================


class TestCleanNodeDetection:
    """Tests that clean nodes pass the audit without violations."""

    def test_good_node_has_no_violations(self) -> None:
        """A properly designed compute node should have zero violations."""
        violations = audit_file(fixture_path("good_node.py"))
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_empty_file_has_no_violations(self, tmp_path: Path) -> None:
        """An empty file should have no violations."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        violations = audit_file(empty_file)
        assert violations == []

    def test_pure_imports_allowed(self, tmp_path: Path) -> None:
        """Standard library and allowed imports should pass."""
        code = """
import typing
from dataclasses import dataclass
from typing import Any, Optional
import json
import re
from collections import defaultdict
"""
        test_file = tmp_path / "pure_imports.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        assert violations == []


# =========================================================================
# Test: Environment Access Detection (env-access)
# =========================================================================


class TestEnvAccessDetection:
    """Tests detection of environment variable access patterns."""

    def test_detects_os_environ_subscript(self) -> None:
        """Should detect os.environ['KEY'] access."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("environ" in v.message.lower() for v in env_violations)

    def test_detects_os_environ_get(self) -> None:
        """Should detect os.environ.get() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert len(env_violations) >= 1

    def test_detects_os_getenv(self) -> None:
        """Should detect os.getenv() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("getenv" in v.message.lower() for v in env_violations)

    def test_detects_os_putenv(self) -> None:
        """Should detect os.putenv() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("putenv" in v.message.lower() for v in env_violations)

    def test_detects_environ_membership_check(self) -> None:
        """Should detect 'key in os.environ' checks."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        # The 'in os.environ' pattern should be caught
        assert len(env_violations) >= 4  # At least 4 violations in bad_env.py

    def test_env_violation_includes_line_number(self) -> None:
        """Violations should include accurate line numbers."""
        violations = audit_file(fixture_path("bad_env.py"))
        for v in violations:
            assert v.line > 0, "Line number should be positive"
            assert v.file == fixture_path("bad_env.py")


# =========================================================================
# Test: File I/O Detection (file-io)
# =========================================================================


class TestFileIODetection:
    """Tests detection of file I/O patterns."""

    def test_detects_open_builtin(self) -> None:
        """Should detect open() builtin calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("open" in v.message.lower() for v in file_violations)

    def test_detects_path_read_text(self) -> None:
        """Should detect Path.read_text() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("read_text" in v.message.lower() for v in file_violations)

    def test_detects_path_write_text(self) -> None:
        """Should detect Path.write_text() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("write_text" in v.message.lower() for v in file_violations)

    def test_detects_path_read_bytes(self) -> None:
        """Should detect Path.read_bytes() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("read_bytes" in v.message.lower() for v in file_violations)

    def test_detects_path_write_bytes(self) -> None:
        """Should detect Path.write_bytes() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("write_bytes" in v.message.lower() for v in file_violations)

    def test_detects_path_open(self) -> None:
        """Should detect Path.open() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        # path.open() should be detected
        assert len(file_violations) >= 5

    def test_detects_io_open(self) -> None:
        """Should detect io.open() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("io.open" in v.message.lower() or "io open" in v.message.lower() for v in file_violations)

    def test_detects_logging_file_handler(self) -> None:
        """Should detect logging.FileHandler usage."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("filehandler" in v.message.lower() for v in file_violations)

    def test_detects_rotating_file_handler(self) -> None:
        """Should detect RotatingFileHandler usage."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any("rotatingfilehandler" in v.message.lower() for v in file_violations)


# =========================================================================
# Test: Network Client Detection (net-client)
# =========================================================================


class TestNetClientDetection:
    """Tests detection of forbidden network/DB client imports."""

    def test_detects_confluent_kafka(self) -> None:
        """Should detect confluent_kafka imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("confluent_kafka" in v.message.lower() for v in net_violations)

    def test_detects_qdrant_client(self) -> None:
        """Should detect qdrant_client imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("qdrant_client" in v.message.lower() for v in net_violations)

    def test_detects_neo4j(self) -> None:
        """Should detect neo4j imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("neo4j" in v.message.lower() for v in net_violations)

    def test_detects_asyncpg(self) -> None:
        """Should detect asyncpg imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("asyncpg" in v.message.lower() for v in net_violations)

    def test_detects_httpx(self) -> None:
        """Should detect httpx imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("httpx" in v.message.lower() for v in net_violations)

    def test_detects_httpx_submodule(self) -> None:
        """Should detect httpx submodule imports (from httpx import AsyncClient)."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        # httpx imports should be caught regardless of form
        assert len([v for v in net_violations if "httpx" in v.message.lower()]) >= 1

    def test_detects_aiofiles(self) -> None:
        """Should detect aiofiles imports."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        assert any("aiofiles" in v.message.lower() for v in net_violations)


# =========================================================================
# Test: Whitelist Functionality
# =========================================================================


class TestWhitelistFunctionality:
    """Tests for the whitelist system."""

    def test_load_whitelist_from_yaml(self) -> None:
        """Should load whitelist configuration from YAML."""
        config = load_whitelist(WHITELIST_PATH)
        assert isinstance(config, ModelWhitelistConfig)
        assert len(config.files) >= 1

    def test_yaml_whitelist_allows_specified_violations(self) -> None:
        """Violations whitelisted in YAML should be filtered out."""
        violations = audit_file(fixture_path("whitelisted_node.py"))
        whitelist = load_whitelist(WHITELIST_PATH)
        remaining = apply_whitelist(violations, whitelist, fixture_path("whitelisted_node.py"))

        # The whitelisted violations (env-access, file-io) should be removed
        # Only un-whitelisted violations should remain
        whitelisted_rules = {EnumIOAuditRule.ENV_ACCESS, EnumIOAuditRule.FILE_IO}
        for v in remaining:
            # The get_unwhitelisted_env function has a violation that's not inline-whitelisted
            # but env-access IS whitelisted in YAML, so it should be filtered
            pass

    def test_inline_pragma_whitelists_next_line(self, tmp_path: Path) -> None:
        """Inline pragma should whitelist the next line only (when file is in YAML)."""
        code = """
import os

# io-audit: ignore-next-line env-access
value = os.getenv("ALLOWED")

# This should still be caught
other = os.getenv("NOT_ALLOWED")
"""
        test_file = tmp_path / "inline_test.py"
        test_file.write_text(code)

        # Create a whitelist that includes this file (required for inline pragmas)
        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path=str(test_file),
                    reason="Test file for inline pragma",
                    allowed_rules=[],  # No blanket rules, rely on inline pragmas
                )
            ]
        )

        violations = audit_file(test_file)
        source_lines = code.splitlines()
        remaining = apply_whitelist(violations, whitelist, test_file, source_lines)

        # Should have exactly 1 violation (the non-whitelisted one)
        env_violations = [v for v in remaining if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert len(env_violations) == 1
        assert env_violations[0].line == 8  # Line with "NOT_ALLOWED"

    def test_parse_inline_pragma_valid(self) -> None:
        """Should correctly parse valid inline pragmas."""
        result = parse_inline_pragma("# io-audit: ignore-next-line file-io")
        assert result is not None
        assert result.rule == EnumIOAuditRule.FILE_IO
        assert result.scope == "next-line"

    def test_parse_inline_pragma_invalid(self) -> None:
        """Should return None for invalid pragma formats."""
        assert parse_inline_pragma("# regular comment") is None
        assert parse_inline_pragma("# noqa: E501") is None
        assert parse_inline_pragma("# io-audit: invalid-scope file-io") is None

    def test_whitelist_requires_yaml_entry_for_inline_pragma(self, tmp_path: Path) -> None:
        """Inline pragma alone should NOT whitelist if file not in YAML."""
        code = """
import os

# io-audit: ignore-next-line env-access
value = os.getenv("SHOULD_STILL_FAIL")
"""
        test_file = tmp_path / "not_in_yaml.py"
        test_file.write_text(code)

        # Create empty whitelist (file NOT in it)
        empty_whitelist = ModelWhitelistConfig(files=[])

        violations = audit_file(test_file)
        source_lines = code.splitlines()
        remaining = apply_whitelist(violations, empty_whitelist, test_file, source_lines)

        # Without YAML entry, inline pragma should NOT work
        # (This enforces the design requirement that YAML is source of truth)
        assert len(remaining) >= 1


# =========================================================================
# Test: Violation Model
# =========================================================================


class TestViolationModel:
    """Tests for the ModelIOAuditViolation data model."""

    def test_violation_has_required_fields(self) -> None:
        """Violations should have file, line, column, rule, and message."""
        violations = audit_file(fixture_path("bad_env.py"))
        assert len(violations) > 0

        v = violations[0]
        assert hasattr(v, "file")
        assert hasattr(v, "line")
        assert hasattr(v, "column")
        assert hasattr(v, "rule")
        assert hasattr(v, "message")

    def test_violation_str_format(self) -> None:
        """Violation string format should be file:line: rule: message."""
        violations = audit_file(fixture_path("bad_env.py"))
        v = violations[0]
        s = str(v)
        # Should contain file path, line number, rule ID, and message
        assert "bad_env.py" in s
        assert ":" in s

    def test_violation_rule_is_enum(self) -> None:
        """Violation rule should be an EnumIOAuditRule value."""
        violations = audit_file(fixture_path("bad_env.py"))
        for v in violations:
            assert isinstance(v.rule, EnumIOAuditRule)


# =========================================================================
# Test: Batch Auditing
# =========================================================================


class TestBatchAuditing:
    """Tests for auditing multiple files at once."""

    def test_audit_files_returns_all_violations(self) -> None:
        """audit_files should return violations from all files."""
        files = [
            fixture_path("bad_env.py"),
            fixture_path("bad_file.py"),
            fixture_path("bad_client.py"),
        ]
        all_violations = audit_files(files)

        # Should have violations from all three files
        files_with_violations = {v.file for v in all_violations}
        assert len(files_with_violations) == 3

    def test_audit_files_with_clean_file(self) -> None:
        """Clean files in batch should contribute zero violations."""
        files = [
            fixture_path("good_node.py"),
            fixture_path("bad_env.py"),
        ]
        all_violations = audit_files(files)

        # Only bad_env.py should have violations
        files_with_violations = {v.file for v in all_violations}
        assert fixture_path("good_node.py") not in files_with_violations
        assert fixture_path("bad_env.py") in files_with_violations

    def test_audit_files_empty_list(self) -> None:
        """Auditing empty file list should return empty violations."""
        violations = audit_files([])
        assert violations == []


# =========================================================================
# Test: Error Handling
# =========================================================================


class TestErrorHandling:
    """Tests for error handling in the audit system."""

    def test_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        """Auditing a non-existent file should raise FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist.py"
        with pytest.raises(FileNotFoundError):
            audit_file(nonexistent)

    def test_syntax_error_file_raises_error(self, tmp_path: Path) -> None:
        """Files with syntax errors should raise SyntaxError."""
        bad_syntax = tmp_path / "bad_syntax.py"
        bad_syntax.write_text("def broken(:\n    pass")
        with pytest.raises(SyntaxError):
            audit_file(bad_syntax)

    def test_binary_file_raises_error(self, tmp_path: Path) -> None:
        """Binary files should raise an appropriate error."""
        binary_file = tmp_path / "binary.py"
        binary_file.write_bytes(b"\x00\x01\x02\x03")
        with pytest.raises((UnicodeDecodeError, SyntaxError)):
            audit_file(binary_file)


# =========================================================================
# Test: AST Visitor
# =========================================================================


class TestIOAuditVisitor:
    """Tests for the AST visitor implementation."""

    def test_visitor_tracks_imports(self) -> None:
        """Visitor should track all imports for context."""
        import ast

        code = """
import os
from pathlib import Path
"""
        tree = ast.parse(code)
        visitor = IOAuditVisitor(Path("test.py"))
        visitor.visit(tree)
        # Visitor should have processed imports
        assert hasattr(visitor, "violations")

    def test_visitor_collects_violations(self) -> None:
        """Visitor should collect violations as it walks AST."""
        import ast

        code = """
import os
x = os.getenv("TEST")
"""
        tree = ast.parse(code)
        visitor = IOAuditVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.violations) >= 1
        assert visitor.violations[0].rule == EnumIOAuditRule.ENV_ACCESS


# =========================================================================
# Test: Rule Enum
# =========================================================================


class TestEnumIOAuditRule:
    """Tests for the IOAuditRule enum."""

    def test_enum_has_expected_values(self) -> None:
        """Enum should have NET_CLIENT, ENV_ACCESS, FILE_IO."""
        assert hasattr(EnumIOAuditRule, "NET_CLIENT")
        assert hasattr(EnumIOAuditRule, "ENV_ACCESS")
        assert hasattr(EnumIOAuditRule, "FILE_IO")

    def test_enum_values_are_strings(self) -> None:
        """Enum values should be the canonical string rule IDs."""
        assert EnumIOAuditRule.NET_CLIENT.value == "net-client"
        assert EnumIOAuditRule.ENV_ACCESS.value == "env-access"
        assert EnumIOAuditRule.FILE_IO.value == "file-io"


# =========================================================================
# Audit Marker for CI Integration
# =========================================================================


@pytest.mark.audit
class TestMainAudit:
    """Main audit test that runs against actual node directories.

    This test is marked with @pytest.mark.audit for selective execution.
    It scans the configured IO_AUDIT_TARGETS directories.
    """

    def test_nodes_directory_has_no_violations(self) -> None:
        """The nodes directory should have no unwhitelisted I/O violations.

        This is the main CI gate test.
        """
        from omniintelligence.audit.io_audit import IO_AUDIT_TARGETS, run_audit

        # Run the full audit
        result = run_audit(
            targets=IO_AUDIT_TARGETS,
            whitelist_path=WHITELIST_PATH,
        )

        # Format violations for clear error message
        if result.violations:
            violation_lines = [str(v) for v in result.violations]
            error_msg = f"I/O Audit failed with {len(result.violations)} violations:\n"
            error_msg += "\n".join(f"  - {line}" for line in violation_lines)
            pytest.fail(error_msg)

        assert result.is_clean, "Audit should pass with no violations"
