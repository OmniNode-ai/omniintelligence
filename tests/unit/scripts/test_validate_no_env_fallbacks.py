# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for validate_no_env_fallbacks.py (OMN-10736)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.validate_no_env_fallbacks import (
    ALLOWLISTED_FILES,
    VIOLATION_PATTERNS,
    _is_comment_or_docstring_line,
    _is_test_file,
)


@pytest.mark.unit
class TestViolationPatterns:
    def test_catches_environ_get_localhost(self) -> None:
        line = 'url = os.environ.get("FOO_URL", "localhost:8080")'
        assert any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_catches_environ_get_private_ip(self) -> None:
        line = 'url = os.environ.get("FOO_URL", "http://192.168.86.201:8001")'
        assert any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_catches_getenv_private_ip(self) -> None:
        line = 'url = os.getenv("LLM_CODER_FAST_URL", "http://192.168.86.201:8001")'
        assert any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_catches_getenv_localhost(self) -> None:
        line = 'url = os.getenv("FOO_URL", "localhost:9000")'
        assert any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_catches_default_localhost(self) -> None:
        line = 'def foo(url: str = "localhost:8080"): ...'
        assert any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_passes_environ_key(self) -> None:
        line = 'url = os.environ["LLM_EMBEDDING_URL"]'
        assert not any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_passes_environ_get_no_fallback(self) -> None:
        line = 'url = os.environ.get("LLM_URL")'
        assert not any(p.search(line) for p in VIOLATION_PATTERNS)

    def test_passes_private_ip_without_fallback_pattern(self) -> None:
        line = (
            'base_url = os.environ["LLM_EMBEDDING_URL"]  # connects to 192.168.86.200'
        )
        assert not any(p.search(line) for p in VIOLATION_PATTERNS)


@pytest.mark.unit
class TestCommentDocstringSkip:
    def test_skips_comment(self) -> None:
        assert _is_comment_or_docstring_line(
            '    # url = os.environ.get("X", "localhost")'
        )

    def test_skips_docstring_triple_double(self) -> None:
        assert _is_comment_or_docstring_line(
            '    """localhost default fallback example"""'
        )

    def test_skips_docstring_triple_single(self) -> None:
        assert _is_comment_or_docstring_line("    '''localhost:8080'''")

    def test_does_not_skip_code(self) -> None:
        assert not _is_comment_or_docstring_line('url = os.getenv("X", "localhost")')


@pytest.mark.unit
class TestTestFileSkip:
    def test_skips_tests_dir(self) -> None:
        path = Path("tests/unit/some_test.py")
        assert _is_test_file(path)

    def test_skips_node_tests_dir(self) -> None:
        path = Path("src/omniintelligence/node_tests/test_foo.py")
        assert _is_test_file(path)

    def test_does_not_skip_src(self) -> None:
        path = Path("src/omniintelligence/clients/embedding_client.py")
        assert not _is_test_file(path)


@pytest.mark.unit
class TestAllowlist:
    def test_validator_itself_is_allowlisted(self) -> None:
        assert "validate_no_env_fallbacks.py" in ALLOWLISTED_FILES

    def test_local_openai_client_is_allowlisted(self) -> None:
        assert "embedding_client_local_openai.py" in ALLOWLISTED_FILES


@pytest.mark.unit
class TestScanIntegration:
    def test_clean_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            src.mkdir()
            clean = src / "clean_module.py"
            clean.write_text(
                '# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.\nimport os\nurl = os.environ["LLM_URL"]\n'
            )
            # Run via subprocess to avoid REPO_ROOT coupling
            import subprocess
            import sys

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"""
import sys
sys.path.insert(0, "{Path(__file__).parent.parent.parent.parent}")
import re
from pathlib import Path
VIOLATION_PATTERNS = [
    re.compile(r'os\\.environ\\.get\\([^)]*["\\'\\']localhost'),
    re.compile(r'os\\.environ\\.get\\([^)]*["\\'\\']http://192\\.168\\.'),
    re.compile(r'os\\.getenv\\([^)]*,\\s*["\\'\\']http://192\\.168\\.'),
    re.compile(r'os\\.getenv\\([^)]*,\\s*["\\'\\']localhost'),
]
content = Path("{clean}").read_text()
for line in content.splitlines():
    for p in VIOLATION_PATTERNS:
        if p.search(line):
            print("VIOLATION:", line)
            sys.exit(1)
print("OK")
""",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stdout + result.stderr

    def test_violating_file_fails(self) -> None:
        import subprocess
        import sys

        violation_code = 'url = os.getenv("LLM_URL", "http://192.168.86.200:8100")\n'
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(violation_code)
            fname = f.name

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import re
from pathlib import Path
VIOLATION_PATTERNS = [
    re.compile(r'os\\.getenv\\([^)]*,\\s*["\\'\\']http://192\\.168\\.'),
]
content = Path("{fname}").read_text()
found = False
for line in content.splitlines():
    for p in VIOLATION_PATTERNS:
        if p.search(line):
            found = True
import sys
sys.exit(1 if found else 0)
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
