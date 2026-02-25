# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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

import ast
from pathlib import Path

import pytest

# Apply audit marker to all tests in this module
pytestmark = pytest.mark.audit

from omniintelligence.audit.io_audit import (
    EnumIOAuditRule,
    IOAuditVisitor,
    ModelWhitelistConfig,
    ModelWhitelistEntry,
    _validate_whitelist_entry,
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

# =========================================================================
# Fixture Violation Inventory (Canonical Reference)
# =========================================================================
# bad_env.py: 9 env-access violations (lines 16,19,22,34,40,46,52,58,64)
# bad_file.py: 11 file-io violations (lines 16,23,30,37,43,49,55,61,68,77,88)
# bad_client.py: 17 net-client violations (9 imports + 6 usages + 2 aliased)
#
# Tests use "at least X" for forward compatibility; use EXPECTED_VIOLATIONS
# for exact counts. Update both comment AND dict if fixtures change.
# =========================================================================

EXPECTED_VIOLATIONS = {
    "bad_env.py": {
        "rule": EnumIOAuditRule.ENV_ACCESS,
        "count": 9,
        "description": "Environment variable access violations",
    },
    "bad_file.py": {
        "rule": EnumIOAuditRule.FILE_IO,
        "count": 11,
        "description": "File I/O operation violations",
    },
    "bad_client.py": {
        "rule": EnumIOAuditRule.NET_CLIENT,
        "count": 17,
        "description": "Network/DB client violations (9 imports + 6 usages + 2 aliased)",
    },
}


def fixture_path(name: str) -> Path:
    """Get path to a test fixture file."""
    return FIXTURES_DIR / name


# =========================================================================
# Test: Fixture Violation Count Verification
# =========================================================================


class TestFixtureViolationCounts:
    """Verify exact violation counts per fixture match EXPECTED_VIOLATIONS."""

    def test_bad_env_violation_count(self) -> None:
        """Verify bad_env.py has exactly 9 env-access violations."""
        expected = EXPECTED_VIOLATIONS["bad_env.py"]
        violations = audit_file(fixture_path("bad_env.py"))
        rule_violations = [v for v in violations if v.rule == expected["rule"]]
        assert len(rule_violations) == expected["count"], (
            f"Expected {expected['count']} {expected['rule'].value} violations, "
            f"got {len(rule_violations)}. See EXPECTED_VIOLATIONS for details."
        )

    def test_bad_file_violation_count(self) -> None:
        """Verify bad_file.py has exactly 11 file-io violations."""
        expected = EXPECTED_VIOLATIONS["bad_file.py"]
        violations = audit_file(fixture_path("bad_file.py"))
        rule_violations = [v for v in violations if v.rule == expected["rule"]]
        assert len(rule_violations) == expected["count"], (
            f"Expected {expected['count']} {expected['rule'].value} violations, "
            f"got {len(rule_violations)}. See EXPECTED_VIOLATIONS for details."
        )

    def test_bad_client_violation_count(self) -> None:
        """Verify bad_client.py has exactly 17 net-client violations."""
        expected = EXPECTED_VIOLATIONS["bad_client.py"]
        violations = audit_file(fixture_path("bad_client.py"))
        rule_violations = [v for v in violations if v.rule == expected["rule"]]
        assert len(rule_violations) == expected["count"], (
            f"Expected {expected['count']} {expected['rule'].value} violations, "
            f"got {len(rule_violations)}. See EXPECTED_VIOLATIONS for details."
        )


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
        # bad_env.py contains 9 distinct env-access violations:
        # 1. os.environ["API_KEY"] (line 16)
        # 2. os.environ.get("TIMEOUT") (line 19)
        # 3. os.getenv("SERVICE_HOST") (line 22)
        # 4. os.putenv(key, value) (line 34)
        # 5. "DEBUG_MODE" in os.environ (line 40)
        # 6. os.environ.pop(key) (line 46)
        # 7. os.environ.setdefault(key, default) (line 52)
        # 8. os.environ.clear() (line 58)
        # 9. os.environ.update(values) (line 64)
        # We check for at least 4 to allow for implementation variations
        assert len(env_violations) >= 4

    def test_detects_os_environ_pop(self) -> None:
        """Should detect os.environ.pop() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("environ.pop" in v.message.lower() for v in env_violations)

    def test_detects_os_environ_setdefault(self) -> None:
        """Should detect os.environ.setdefault() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("environ.setdefault" in v.message.lower() for v in env_violations)

    def test_detects_os_environ_clear(self) -> None:
        """Should detect os.environ.clear() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("environ.clear" in v.message.lower() for v in env_violations)

    def test_detects_os_environ_update(self) -> None:
        """Should detect os.environ.update() calls."""
        violations = audit_file(fixture_path("bad_env.py"))
        env_violations = [v for v in violations if v.rule == EnumIOAuditRule.ENV_ACCESS]
        assert any("environ.update" in v.message.lower() for v in env_violations)

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
        # bad_file.py contains 11 distinct file-io violations:
        # 1. RotatingFileHandler import (line 16)
        # 2. open(path) read (line 23)
        # 3. open(path, "w") write (line 30)
        # 4. path.read_text() (line 37)
        # 5. path.write_text() (line 43)
        # 6. path.read_bytes() (line 49)
        # 7. path.write_bytes() (line 55)
        # 8. path.open() (line 61)
        # 9. io.open(path) (line 68)
        # 10. logging.FileHandler("node.log") (line 77)
        # 11. RotatingFileHandler(...) (line 88)
        # We check for at least 5 to cover core file I/O patterns
        assert len(file_violations) >= 5

    def test_detects_io_open(self) -> None:
        """Should detect io.open() calls."""
        violations = audit_file(fixture_path("bad_file.py"))
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert any(
            "io.open" in v.message.lower() or "io open" in v.message.lower()
            for v in file_violations
        )

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
# Test: Pathlib False Positive Prevention
# =========================================================================


class TestPathlibFalsePositivePrevention:
    """Tests that custom objects with pathlib-like method names don't trigger false positives."""

    def test_no_false_positive_for_custom_read_text_without_pathlib_import(
        self, tmp_path: Path
    ) -> None:
        """Custom object with read_text() should NOT trigger violation when pathlib not imported."""
        code = '''
class CustomReader:
    """A custom class with read_text method that is NOT pathlib-related."""

    def read_text(self) -> str:
        """Read from a database or API, not a file."""
        return "data from api"

def process_data():
    reader = CustomReader()
    # This should NOT be flagged - no pathlib import
    content = reader.read_text()
    return content
'''
        test_file = tmp_path / "custom_reader.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 0, f"Unexpected violations: {file_violations}"

    def test_no_false_positive_for_custom_write_text_without_pathlib_import(
        self, tmp_path: Path
    ) -> None:
        """Custom object with write_text() should NOT trigger violation when pathlib not imported."""
        code = '''
class CustomWriter:
    """A custom class with write_text method for API calls."""

    def write_text(self, content: str) -> None:
        """Write to a database or API, not a file."""
        pass

def save_data(data: str):
    writer = CustomWriter()
    # This should NOT be flagged - no pathlib import
    writer.write_text(data)
'''
        test_file = tmp_path / "custom_writer.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 0, f"Unexpected violations: {file_violations}"

    def test_no_false_positive_for_mock_path_object(self, tmp_path: Path) -> None:
        """Mock Path objects in tests should NOT trigger violations without pathlib import."""
        code = '''
class MockPath:
    """Mock Path for testing purposes."""

    def read_text(self) -> str:
        return "mocked content"

    def write_text(self, content: str) -> None:
        pass

    def read_bytes(self) -> bytes:
        return b"mocked bytes"

def test_something():
    mock = MockPath()
    # None of these should trigger violations
    content = mock.read_text()
    mock.write_text("test")
    data = mock.read_bytes()
'''
        test_file = tmp_path / "test_mock_path.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 0, f"Unexpected violations: {file_violations}"

    def test_detects_pathlib_io_when_path_imported(self, tmp_path: Path) -> None:
        """Should still detect pathlib I/O when Path is properly imported."""
        code = """
from pathlib import Path

def read_config():
    path = Path("config.yaml")
    # This SHOULD be flagged - pathlib imported and variable named "path"
    return path.read_text()
"""
        test_file = tmp_path / "uses_pathlib.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 1, (
            f"Expected 1 violation, got: {file_violations}"
        )
        assert "read_text" in file_violations[0].message.lower()

    def test_detects_pathlib_io_with_path_constructor_chain(
        self, tmp_path: Path
    ) -> None:
        """Should detect Path().read_text() chained calls."""
        code = """
from pathlib import Path

def read_inline():
    # Direct Path() constructor chained with read_text
    return Path("data.txt").read_text()
"""
        test_file = tmp_path / "path_chain.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 1, (
            f"Expected 1 violation, got: {file_violations}"
        )

    def test_detects_pathlib_io_with_file_path_variable(self, tmp_path: Path) -> None:
        """Should detect pathlib I/O on variables named file_path, config_path, etc."""
        code = """
from pathlib import Path

def read_config(config_path):
    # Variable named config_path is likely a Path object
    return config_path.read_text()
"""
        test_file = tmp_path / "config_reader.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 1, (
            f"Expected 1 violation, got: {file_violations}"
        )

    def test_no_false_positive_for_arbitrary_variable_without_pathlib(
        self, tmp_path: Path
    ) -> None:
        """Arbitrary objects with read_text should not trigger without pathlib import."""
        code = """
class TextProcessor:
    def read_text(self):
        return "processed"

processor = TextProcessor()
result = processor.read_text()  # Should NOT be flagged
"""
        test_file = tmp_path / "text_processor.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 0, f"Unexpected violations: {file_violations}"

    def test_short_variable_name_with_pathlib_triggers_violation(
        self, tmp_path: Path
    ) -> None:
        """Short variable names like 'p' should trigger when pathlib is imported.

        PATHLIB_VARIABLE_PATTERNS includes short names like 'p' and 'fp' which
        are commonly used for Path objects. When pathlib is imported, these
        should be flagged.

        Note: This is intentional behavior - in code that imports pathlib,
        variables named 'p' are very likely Path objects. This may cause
        rare false positives, but the benefit of catching real violations
        outweighs the occasional false positive.
        """
        code = """
from pathlib import Path

def read_file(p):
    # Variable 'p' is in PATHLIB_VARIABLE_PATTERNS and pathlib is imported
    # This SHOULD be flagged as a potential violation
    return p.read_text()
"""
        test_file = tmp_path / "short_var.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        # Should detect the p.read_text() call
        assert len(file_violations) == 1, (
            f"Expected 1 violation, got: {file_violations}"
        )
        assert "read_text" in file_violations[0].message.lower()

    def test_short_variable_name_without_pathlib_no_false_positive(
        self, tmp_path: Path
    ) -> None:
        """Short variable names should NOT trigger when pathlib is NOT imported.

        This test ensures that even with short variable names like 'p', we don't
        get false positives when pathlib is not imported. The heuristic only
        applies when pathlib is in scope.
        """
        code = """
class Printer:
    def read_text(self):
        return "printed"

def print_stuff(p):
    # Variable 'p' is in PATHLIB_VARIABLE_PATTERNS but pathlib is NOT imported
    # This should NOT be flagged
    return p.read_text()
"""
        test_file = tmp_path / "no_pathlib.py"
        test_file.write_text(code)
        violations = audit_file(test_file)
        file_violations = [v for v in violations if v.rule == EnumIOAuditRule.FILE_IO]
        assert len(file_violations) == 0, f"Unexpected violations: {file_violations}"


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

    def test_detects_aliased_httpx_usage(self) -> None:
        """Should detect httpx usage via alias (import httpx as http_client)."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        # Should detect: http_client.get(url) where http_client is aliased httpx
        alias_violations = [v for v in net_violations if "http_client" in v.message]
        assert len(alias_violations) >= 1, (
            f"Expected at least 1 aliased httpx violation, got: {alias_violations}"
        )
        # Verify the message includes the alias and original module info
        assert any("alias" in v.message.lower() for v in alias_violations)

    def test_detects_aliased_confluent_kafka_usage(self) -> None:
        """Should detect confluent_kafka usage via alias (import confluent_kafka as ck)."""
        violations = audit_file(fixture_path("bad_client.py"))
        net_violations = [v for v in violations if v.rule == EnumIOAuditRule.NET_CLIENT]
        # Should detect: ck.Producer({}) where ck is aliased confluent_kafka
        alias_violations = [
            v for v in net_violations if "ck.producer" in v.message.lower()
        ]
        assert len(alias_violations) >= 1, (
            f"Expected at least 1 aliased confluent_kafka violation, got: {alias_violations}"
        )

    def test_aliased_import_violations_have_correct_rule(self) -> None:
        """Aliased import usage violations should have NET_CLIENT rule."""
        violations = audit_file(fixture_path("bad_client.py"))
        alias_violations = [v for v in violations if "alias" in v.message.lower()]
        for v in alias_violations:
            assert v.rule == EnumIOAuditRule.NET_CLIENT, (
                f"Expected NET_CLIENT rule for alias violation, got: {v.rule}"
            )


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
        remaining = apply_whitelist(
            violations, whitelist, fixture_path("whitelisted_node.py")
        )

        # The whitelisted violations (env-access, file-io) should be removed
        # Only un-whitelisted violations should remain
        # Verify that whitelisted rules are not in the remaining violations
        whitelisted_rules = {EnumIOAuditRule.ENV_ACCESS, EnumIOAuditRule.FILE_IO}
        for violation in remaining:
            # The get_unwhitelisted_env function has a violation that's not inline-whitelisted
            # but env-access IS whitelisted in YAML, so it should be filtered
            assert violation.rule not in whitelisted_rules, (
                f"Whitelisted rule {violation.rule} should have been filtered"
            )

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
        # Verify the violation is from the line with "NOT_ALLOWED" by checking message content
        # Using message content is more robust than hardcoding line numbers which can drift
        assert "getenv" in env_violations[0].message.lower()
        # The non-whitelisted call should be on the line after the comment (line 8 in this test)
        # We use the comment as an anchor: find "This should still be caught" and verify
        # the violation is on the next non-empty line
        comment_line = next(
            i
            for i, line in enumerate(source_lines, start=1)
            if "This should still be caught" in line
        )
        expected_violation_line = comment_line + 1
        assert env_violations[0].line == expected_violation_line

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

    def test_whitelist_requires_yaml_entry_for_inline_pragma(
        self, tmp_path: Path
    ) -> None:
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
        remaining = apply_whitelist(
            violations, empty_whitelist, test_file, source_lines
        )

        # Without YAML entry, inline pragma should NOT work
        # (This enforces the design requirement that YAML is source of truth)
        assert len(remaining) >= 1


# =========================================================================
# Test: Whitelist Entry Validation
# =========================================================================


class TestWhitelistEntryValidation:
    """Tests for whitelist entry validation."""

    def test_empty_reason_raises_error(self) -> None:
        """Empty reason field should raise ValueError."""
        entry = ModelWhitelistEntry(
            path="some_file.py",
            reason="",
            allowed_rules=["env-access"],
        )
        with pytest.raises(ValueError) as exc_info:
            _validate_whitelist_entry(entry)

        assert "Empty 'reason' field" in str(exc_info.value)
        assert "some_file.py" in str(exc_info.value)

    def test_whitespace_only_reason_raises_error(self) -> None:
        """Whitespace-only reason field should raise ValueError."""
        entry = ModelWhitelistEntry(
            path="another_file.py",
            reason="   \t\n  ",
            allowed_rules=["file-io"],
        )
        with pytest.raises(ValueError) as exc_info:
            _validate_whitelist_entry(entry)

        assert "Empty 'reason' field" in str(exc_info.value)
        assert "another_file.py" in str(exc_info.value)

    def test_valid_reason_passes_validation(self) -> None:
        """Valid non-empty reason should pass validation."""
        entry = ModelWhitelistEntry(
            path="valid_file.py",
            reason="Effect node requires Kafka client for event publishing",
            allowed_rules=["net-client"],
        )
        # Should not raise
        _validate_whitelist_entry(entry)

    def test_invalid_rule_id_raises_error(self) -> None:
        """Invalid rule ID should raise ValueError."""
        entry = ModelWhitelistEntry(
            path="file.py",
            reason="Valid reason",
            allowed_rules=["invalid-rule"],
        )
        with pytest.raises(ValueError) as exc_info:
            _validate_whitelist_entry(entry)

        assert "Invalid rule ID 'invalid-rule'" in str(exc_info.value)

    def test_load_whitelist_with_empty_reason_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Loading a whitelist YAML with empty reason should raise ValueError."""
        whitelist_yaml = tmp_path / "whitelist.yaml"
        whitelist_yaml.write_text("""
schema_version: "1.0.0"
files:
  - path: "some_node.py"
    reason: ""
    allowed_rules:
      - env-access
""")
        with pytest.raises(ValueError) as exc_info:
            load_whitelist(whitelist_yaml)

        assert "Empty 'reason' field" in str(exc_info.value)
        assert "some_node.py" in str(exc_info.value)

    def test_load_whitelist_with_missing_reason_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Loading a whitelist YAML with missing reason should raise ValueError."""
        whitelist_yaml = tmp_path / "whitelist.yaml"
        whitelist_yaml.write_text("""
schema_version: "1.0.0"
files:
  - path: "some_node.py"
    allowed_rules:
      - env-access
""")
        with pytest.raises(ValueError) as exc_info:
            load_whitelist(whitelist_yaml)

        assert "Empty 'reason' field" in str(exc_info.value)


# =========================================================================
# Test: Whitelist Pattern Matching Security
# =========================================================================


class TestWhitelistPatternMatchingSecurity:
    """Tests for secure whitelist pattern matching.

    These tests ensure that whitelist entries with specific file names
    do not accidentally match files with similar names, preventing
    security holes in the whitelist system.
    """

    def test_exact_filename_match_works(self, tmp_path: Path) -> None:
        """Whitelisting 'bad_node.py' should match exactly 'bad_node.py'."""
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "bad_node.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="bad_node.py",
                    reason="Test exact match",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have no violations - exact match should work
        assert len(remaining) == 0, f"Expected whitelist to apply, got: {remaining}"

    def test_similar_filename_not_matched(self, tmp_path: Path) -> None:
        """Whitelisting 'bad_node.py' should NOT match 'my_bad_node.py'.

        This is a critical security test - the old pattern f"*{entry.path}"
        would incorrectly match 'my_bad_node.py' when only 'bad_node.py'
        was whitelisted.
        """
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "my_bad_node.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="bad_node.py",
                    reason="Only whitelist exact file",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have violations - similar name should NOT match
        assert len(remaining) > 0, "Similar filename should NOT be whitelisted"

    def test_backup_file_not_matched(self, tmp_path: Path) -> None:
        """Whitelisting 'bad_node.py' should NOT match 'bad_node.py.backup'.

        This is another security test - ensures file extensions/suffixes
        don't cause unintended matches.
        """
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "bad_node.py.backup"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="bad_node.py",
                    reason="Only whitelist exact file",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have violations - backup file should NOT match
        assert len(remaining) > 0, "Backup file should NOT be whitelisted"

    def test_glob_pattern_still_works(self, tmp_path: Path) -> None:
        """Glob patterns like 'legacy_*.py' should still work correctly."""
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "legacy_foo.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="legacy_*.py",
                    reason="Whitelist all legacy files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have no violations - glob should match
        assert len(remaining) == 0, f"Glob pattern should match, got: {remaining}"

    def test_glob_pattern_with_question_mark(self, tmp_path: Path) -> None:
        """Glob patterns with '?' wildcard should work correctly."""
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "node_v1.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="node_v?.py",
                    reason="Whitelist all version files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have no violations - ? pattern should match
        assert len(remaining) == 0, f"? pattern should match, got: {remaining}"

    def test_relative_path_matching(self, tmp_path: Path) -> None:
        """Relative paths like 'nodes/whitelisted_node.py' should work."""
        subdir = tmp_path / "nodes"
        subdir.mkdir()

        code = """
import os
value = os.getenv("TEST")
"""
        test_file = subdir / "whitelisted_node.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="nodes/whitelisted_node.py",
                    reason="Whitelist specific path",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have no violations - relative path should match
        assert len(remaining) == 0, f"Relative path should match, got: {remaining}"

    def test_full_path_matching(self, tmp_path: Path) -> None:
        """Full absolute paths should match exactly."""
        code = """
import os
value = os.getenv("TEST")
"""
        test_file = tmp_path / "specific_node.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path=str(test_file),
                    reason="Whitelist full path",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        # Should have no violations - full path should match
        assert len(remaining) == 0, f"Full path should match, got: {remaining}"

    def test_glob_pattern_does_not_match_similar_names_incorrectly(
        self, tmp_path: Path
    ) -> None:
        """Glob pattern '*.py' should match 'foo.py' but NOT 'foo.py.txt'."""
        code = """
import os
value = os.getenv("TEST")
"""
        # Create a .py file - should match
        py_file = tmp_path / "foo.py"
        py_file.write_text(code)

        # Create a .py.txt file - should NOT match
        txt_file = tmp_path / "foo.py.txt"
        txt_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="*.py",
                    reason="Whitelist all Python files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        # .py file should be whitelisted
        violations = audit_file(py_file)
        remaining = apply_whitelist(violations, whitelist, py_file)
        assert len(remaining) == 0, f"*.py should match foo.py, got: {remaining}"

        # .py.txt file should NOT be whitelisted
        violations = audit_file(txt_file)
        remaining = apply_whitelist(violations, whitelist, txt_file)
        assert len(remaining) > 0, "*.py should NOT match foo.py.txt"

    def test_recursive_glob_pattern_matches_nested_files(self, tmp_path: Path) -> None:
        """Pattern '**/test_*.py' should match files in any subdirectory."""
        # Create nested directory structure
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)

        code = """
import os
value = os.getenv("TEST")
"""
        test_file = nested / "test_something.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="**/test_*.py",
                    reason="Whitelist all test files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        assert len(remaining) == 0, f"Recursive glob should match, got: {remaining}"

    def test_recursive_glob_matches_at_any_depth(self, tmp_path: Path) -> None:
        """Pattern '**/nodes/**/*.py' should match at any depth."""
        # Create: tmp/src/nodes/deep/node.py
        deep = tmp_path / "src" / "nodes" / "deep"
        deep.mkdir(parents=True)

        code = """
import os
value = os.getenv("TEST")
"""
        test_file = deep / "node.py"
        test_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="**/nodes/**/*.py",
                    reason="Whitelist all node files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(test_file)
        remaining = apply_whitelist(violations, whitelist, test_file)

        assert len(remaining) == 0

    def test_recursive_glob_does_not_match_wrong_pattern(self, tmp_path: Path) -> None:
        """Pattern '**/test_*.py' should NOT match 'prod_foo.py'."""
        code = """
import os
value = os.getenv("TEST")
"""
        prod_file = tmp_path / "prod_foo.py"
        prod_file.write_text(code)

        whitelist = ModelWhitelistConfig(
            files=[
                ModelWhitelistEntry(
                    path="**/test_*.py",
                    reason="Only test files",
                    allowed_rules=["env-access"],
                )
            ]
        )

        violations = audit_file(prod_file)
        remaining = apply_whitelist(violations, whitelist, prod_file)

        assert len(remaining) > 0, "Non-matching file should NOT be whitelisted"


# =========================================================================
# Test: Symlink Handling
# =========================================================================


class TestSymlinkHandling:
    """Tests for symlink behavior in the audit.

    Symlink Handling Policy
    -----------------------
    The I/O audit handles symlinks as follows:

    **For audit_file() (single file audit):**
    - Symlinks to files are followed and the target file is audited
    - Broken symlinks raise FileNotFoundError (target doesn't exist)
    - The violation reports use the original symlink path, not the resolved path

    **For discover_python_files() (directory scanning):**
    - Symlinks to files are resolved to canonical paths for deduplication
    - Symlinks to directories are NOT followed (Python's rglob security behavior)
    - Broken symlinks are skipped gracefully (is_file() returns False)
    - Circular symlinks are skipped gracefully (resolve() raises RuntimeError)
    - This prevents infinite loops and duplicate processing

    **Why directory symlinks are not followed:**
    Python's ``pathlib.Path.rglob()`` does not follow symlinks to directories
    by default. This is a security feature to prevent:

    - Symlink attacks that could access files outside the intended tree
    - Infinite loops from circular directory symlinks
    - Unpredictable traversal behavior

    If you need to audit files in a symlinked directory, add that directory
    to the targets list directly.

    **Security Considerations:**
    - Symlink resolution prevents auditing the same file twice via different paths
    - Circular symlink protection prevents resource exhaustion attacks
    - Not following directory symlinks prevents symlink escape attacks
    """

    def test_audit_follows_symlink_to_file(self, tmp_path: Path) -> None:
        """Audit should follow symlinks and audit the target file."""
        # Create a real file with violations
        real_file = tmp_path / "real_file.py"
        real_file.write_text("import os\nx = os.getenv('TEST')")

        # Create symlink
        symlink = tmp_path / "link.py"
        symlink.symlink_to(real_file)

        violations = audit_file(symlink)
        assert len(violations) > 0

    def test_audit_broken_symlink_raises_error(self, tmp_path: Path) -> None:
        """Broken symlinks should raise FileNotFoundError."""
        broken_link = tmp_path / "broken.py"
        broken_link.symlink_to(tmp_path / "nonexistent.py")

        with pytest.raises(FileNotFoundError):
            audit_file(broken_link)

    def test_discover_skips_circular_symlinks_gracefully(self, tmp_path: Path) -> None:
        """Circular symlinks should be skipped without error.

        A circular symlink is one that eventually points back to itself,
        either directly (a -> a) or through a chain (a -> b -> c -> a).
        The discover_python_files function should skip these to prevent
        infinite loops during directory traversal.
        """
        from omniintelligence.audit.io_audit import discover_python_files

        # Create a directory structure
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create a real Python file
        real_file = nodes_dir / "real_node.py"
        real_file.write_text("# Valid Python file")

        # Create a self-referencing circular symlink
        # Note: On most systems, symlink_to with target=self creates a broken link
        # but we handle it the same way as circular
        circular_link = nodes_dir / "circular.py"
        circular_link.symlink_to(circular_link)

        # Should complete without raising any error
        files = discover_python_files([str(nodes_dir)])

        # Should find the real file but not the circular symlink
        assert len(files) == 1
        assert files[0].name == "real_node.py"

    def test_discover_skips_broken_symlinks_gracefully(self, tmp_path: Path) -> None:
        """Broken symlinks in directory traversal should be skipped without error.

        Unlike audit_file() which raises FileNotFoundError for broken symlinks,
        discover_python_files() should skip them silently to allow the audit
        to continue processing valid files.
        """
        from omniintelligence.audit.io_audit import discover_python_files

        # Create a directory structure
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create a real Python file
        real_file = nodes_dir / "real_node.py"
        real_file.write_text("# Valid Python file")

        # Create a broken symlink (points to non-existent file)
        broken_link = nodes_dir / "broken.py"
        broken_link.symlink_to(nodes_dir / "does_not_exist.py")

        # Should complete without raising any error
        files = discover_python_files([str(nodes_dir)])

        # Should find only the real file
        assert len(files) == 1
        assert files[0].name == "real_node.py"

    def test_discover_does_not_follow_directory_symlinks(self, tmp_path: Path) -> None:
        """Symlinks to directories are not followed during discovery.

        Python's rglob() does not follow symlinks to directories for security
        reasons. If you need to audit files in a symlinked directory, add that
        directory to the targets list directly.
        """
        from omniintelligence.audit.io_audit import discover_python_files

        # Create main nodes directory
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create a separate directory with Python files
        external_dir = tmp_path / "external_nodes"
        external_dir.mkdir()
        external_file = external_dir / "external_node.py"
        external_file.write_text("# External node")

        # Create a symlink from nodes/ to external_nodes/
        linked_dir = nodes_dir / "linked"
        linked_dir.symlink_to(external_dir)

        # Should NOT find the file through the symlinked directory
        # (rglob does not follow directory symlinks)
        files = discover_python_files([str(nodes_dir)])

        # No files should be found (the only Python file is through the symlink)
        assert len(files) == 0

        # But if we add the external directory directly, it should work
        files = discover_python_files([str(nodes_dir), str(external_dir)])
        assert len(files) == 1
        assert files[0].name == "external_node.py"

    def test_discover_deduplicates_symlinked_files(self, tmp_path: Path) -> None:
        """Files reachable via multiple paths should only be audited once.

        If the same file is accessible via both a direct path and a symlink,
        discover_python_files() should deduplicate to avoid redundant auditing.
        """
        from omniintelligence.audit.io_audit import discover_python_files

        # Create directory structure
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create a Python file
        original_file = nodes_dir / "original.py"
        original_file.write_text("# Original file")

        # Create a symlink to the same file
        link_file = nodes_dir / "link_to_original.py"
        link_file.symlink_to(original_file)

        # Discover files
        files = discover_python_files([str(nodes_dir)])

        # Should only find one file (deduplicated by canonical path)
        assert len(files) == 1
        assert files[0].name == "original.py"

    def test_symlink_violation_reports_symlink_path(self, tmp_path: Path) -> None:
        """Violation reports should include the symlink path, not the resolved path.

        When auditing via a symlink, the violation should report the path
        that was passed to audit_file(), making it easier to locate the issue.
        """
        # Create a real file with violations
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        real_file = real_dir / "target.py"
        real_file.write_text("import os\nx = os.getenv('TEST')")

        # Create symlink in a different location
        link_dir = tmp_path / "links"
        link_dir.mkdir()
        symlink = link_dir / "linked_node.py"
        symlink.symlink_to(real_file)

        violations = audit_file(symlink)

        # Violation should report the symlink path
        assert len(violations) > 0
        assert "linked_node.py" in str(violations[0].file)


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

    def test_non_utf8_file_raises_error_with_file_path(self, tmp_path: Path) -> None:
        """Non-UTF8 files should raise UnicodeDecodeError with file path in message."""
        # Create a file with Latin-1 encoded content (valid Latin-1, invalid UTF-8)
        non_utf8_file = tmp_path / "non_utf8.py"
        # This is valid Python but uses Latin-1 encoding with a non-UTF8 character
        non_utf8_file.write_bytes(b"# Comment with accent: caf\xe9\nx = 1\n")

        with pytest.raises(UnicodeDecodeError) as exc_info:
            audit_file(non_utf8_file)

        # Verify the enhanced error message includes the file path
        error_reason = exc_info.value.reason
        assert "non_utf8.py" in error_reason
        assert "non-UTF8" in error_reason or "UTF-8" in error_reason


# =========================================================================
# Test: AST Visitor
# =========================================================================


class TestIOAuditVisitor:
    """Tests for the AST visitor implementation."""

    def test_visitor_tracks_imports(self) -> None:
        """Visitor should track all imports for context."""
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


class TestMainAudit:
    """Main audit test that runs against actual node directories.

    This test is marked with @pytest.mark.audit via module-level pytestmark
    for selective execution. It scans the configured IO_AUDIT_TARGETS directories.
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


# =========================================================================
# Test: Security Pattern Validation
# =========================================================================


class TestOverlyPermissivePatternDetection:
    """Tests for detecting overly permissive whitelist patterns.

    Overly broad patterns like **/*.py can create security vulnerabilities
    by inadvertently whitelisting more files than intended.
    """

    def test_check_pattern_security_detects_all_py_files(self) -> None:
        """Pattern '**/*.py' should be flagged as dangerous."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security("**/*.py")
        assert warning is not None
        assert "ALL files" in warning or "overly broad" in warning.lower()

    def test_check_pattern_security_detects_bare_wildcard(self) -> None:
        """Pattern '*.py' without directory should be flagged."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security("*.py")
        assert warning is not None
        # *.py is caught as a known dangerous pattern (matches ALL .py files)
        assert "ALL files" in warning or "disables" in warning.lower()

    def test_check_pattern_security_detects_wildcard_without_directory(self) -> None:
        """Pattern '*_node.py' without directory prefix should be flagged."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security("*_node.py")
        assert warning is not None
        # Caught by Rule 2: starts with wildcard, no directory prefix
        assert "wildcard" in warning.lower() or "directory" in warning.lower()

    def test_check_pattern_security_detects_star_star_star(self) -> None:
        """Pattern '**/*' should be flagged as matching everything."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security("**/*")
        assert warning is not None
        assert "ALL files" in warning

    def test_check_pattern_security_allows_specific_path(self) -> None:
        """Specific file paths should not be flagged."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security(
            "src/omniintelligence/nodes/kafka_publisher/v1_0_0/node.py"
        )
        assert warning is None

    def test_check_pattern_security_allows_scoped_glob(self) -> None:
        """Glob patterns with directory prefix should be allowed."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security("nodes/legacy_*.py")
        assert warning is None

    def test_check_pattern_security_allows_versioned_glob(self) -> None:
        """Versioned glob patterns should be allowed."""
        from omniintelligence.audit.io_audit import _check_pattern_security

        warning = _check_pattern_security(
            "src/omniintelligence/nodes/kafka_publisher/v*/node.py"
        )
        assert warning is None

    def test_load_whitelist_warns_on_permissive_pattern(self, tmp_path: Path) -> None:
        """Loading a whitelist with overly permissive pattern should warn."""
        import warnings

        whitelist_file = tmp_path / "whitelist.yaml"
        whitelist_file.write_text("""
schema_version: "1.0.0"
files:
  - path: "**/*.py"
    reason: "Testing dangerous pattern"
    allowed_rules:
      - "net-client"
""")

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            load_whitelist(whitelist_file)

            # Check that a warning was raised
            assert len(w) >= 1
            warning_messages = [str(warning.message) for warning in w]
            assert any(
                "SECURITY WARNING" in msg or "permissive" in msg.lower()
                for msg in warning_messages
            ), f"Expected security warning, got: {warning_messages}"

    def test_load_whitelist_no_warning_for_safe_pattern(self, tmp_path: Path) -> None:
        """Loading a whitelist with safe patterns should not warn."""
        import warnings

        whitelist_file = tmp_path / "whitelist.yaml"
        whitelist_file.write_text("""
schema_version: "1.0.0"
files:
  - path: "tests/audit/fixtures/io/specific_node.py"
    reason: "Test fixture for specific functionality"
    allowed_rules:
      - "env-access"
""")

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            load_whitelist(whitelist_file)

            # Filter for our security warnings only
            security_warnings = [
                warning for warning in w if "SECURITY WARNING" in str(warning.message)
            ]
            assert len(security_warnings) == 0, (
                f"Expected no security warnings, got: {security_warnings}"
            )
