# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for validate_no_env_fallbacks.py (OMN-10736)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_no_env_fallbacks import (
    PYTHON_FALLBACK_PATTERNS,
    SKIP_FILES,
    _is_pure_comment,
    _should_skip,
    run_on_files,
    scan_python_file,
)


@pytest.mark.unit
class TestViolationPatterns:
    def test_catches_environ_get_localhost(self) -> None:
        line = 'url = os.environ.get("FOO_URL", "localhost:8080")'
        assert any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_catches_environ_get_private_ip(self) -> None:
        line = 'url = os.environ.get("FOO_URL", "http://192.168.86.201:8001")'
        assert any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_catches_getenv_private_ip(self) -> None:
        line = 'url = os.getenv("LLM_CODER_FAST_URL", "http://192.168.86.201:8001")'
        assert any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_catches_getenv_localhost(self) -> None:
        line = 'url = os.getenv("FOO_URL", "localhost:9000")'
        assert any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_catches_default_localhost(self) -> None:
        line = 'def foo(url: str = "localhost:8080"): ...'
        assert any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_passes_environ_key(self) -> None:
        line = 'url = os.environ["LLM_EMBEDDING_URL"]'
        assert not any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_passes_environ_get_no_fallback(self) -> None:
        line = 'url = os.environ.get("LLM_URL")'
        assert not any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)

    def test_passes_private_ip_without_fallback_pattern(self) -> None:
        line = (
            'base_url = os.environ["LLM_EMBEDDING_URL"]  # connects to 192.168.86.200'
        )
        assert not any(p.search(line) for p in PYTHON_FALLBACK_PATTERNS)


@pytest.mark.unit
class TestCommentDocstringSkip:
    def test_skips_comment(self) -> None:
        assert _is_pure_comment('    # url = os.environ.get("X", "localhost")')

    def test_skips_single_line_triple_double_docstring(self, tmp_path: Path) -> None:
        path = tmp_path / "module.py"
        path.write_text(
            '"""url = os.getenv("X", "localhost")"""\nurl = os.environ["LLM_URL"]\n',
            encoding="utf-8",
        )
        assert scan_python_file(path) == []

    def test_skips_multiline_docstring_closing_line(self, tmp_path: Path) -> None:
        path = tmp_path / "module.py"
        path.write_text(
            '"""example\n'
            'url = os.getenv("X", "localhost")\n'
            'closing localhost:8080"""\n'
            'url = os.environ["LLM_URL"]\n',
            encoding="utf-8",
        )
        assert scan_python_file(path) == []

    def test_scans_code(self, tmp_path: Path) -> None:
        path = tmp_path / "module.py"
        path.write_text('url = os.getenv("X", "localhost")\n', encoding="utf-8")
        assert scan_python_file(path) == [(1, 'url = os.getenv("X", "localhost")')]


@pytest.mark.unit
class TestTestFileSkip:
    def test_skips_tests_dir(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        path = repo_root / "tests" / "unit" / "some_test.py"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        assert _should_skip(path, repo_root)

    def test_skips_node_tests_dir(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        path = repo_root / "src" / "omniintelligence" / "node_tests" / "test_foo.py"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        assert _should_skip(path, repo_root)

    def test_does_not_skip_src(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        path = (
            repo_root / "src" / "omniintelligence" / "clients" / "embedding_client.py"
        )
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        assert not _should_skip(path, repo_root)


@pytest.mark.unit
class TestAllowlist:
    def test_validator_itself_is_allowlisted(self) -> None:
        assert "validate_no_env_fallbacks.py" in SKIP_FILES


@pytest.mark.unit
class TestScanIntegration:
    def test_clean_file_passes(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        clean = repo_root / "src" / "clean_module.py"
        clean.parent.mkdir()
        clean.write_text(
            "# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.\n"
            "import os\n"
            'url = os.environ["LLM_URL"]\n',
            encoding="utf-8",
        )
        assert run_on_files([clean], repo_root) == []

    def test_violating_file_fails(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        violating = repo_root / "src" / "violating_module.py"
        violating.parent.mkdir()
        violating.write_text(
            'url = os.getenv("LLM_URL", "http://192.168.86.200:8100")\n',
            encoding="utf-8",
        )
        assert run_on_files([violating], repo_root) == [
            (
                "src/violating_module.py",
                1,
                'url = os.getenv("LLM_URL", "http://192.168.86.200:8100")',
            )
        ]
