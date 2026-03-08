# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for CI fingerprint handler.

Ticket: OMN-3556
"""

import pytest

from omniintelligence.nodes.node_ci_fingerprint_compute.handlers.handler_fingerprint import (
    _extract_frames,
    compute_error_fingerprint,
)


@pytest.mark.unit
def test_extract_frames_uses_two_path_components() -> None:
    """Two files with same basename but different packages must not collide."""
    traceback = """
  File "/app/pkg_a/foo.py", line 42, in handle_event
    result = do_thing()
  File "/app/pkg_b/foo.py", line 17, in do_thing
    return bad_call()
"""
    frames = _extract_frames(traceback)
    assert "pkg_a/foo.py:handle_event" in frames
    assert "pkg_b/foo.py:do_thing" in frames
    # Basename-only collision would make these identical — they must differ
    assert frames[0] != frames[1]


@pytest.mark.unit
def test_extract_frames_strips_line_numbers() -> None:
    """Line numbers must be stripped — same error on different lines = same frame."""
    traceback_v1 = '  File "/app/pkg/bar.py", line 10, in handle\n    x = bad()\n'
    traceback_v2 = '  File "/app/pkg/bar.py", line 99, in handle\n    x = bad()\n'
    assert _extract_frames(traceback_v1) == _extract_frames(traceback_v2)


@pytest.mark.unit
def test_extract_frames_strips_memory_addresses() -> None:
    """Memory addresses must not affect frame identity."""
    tb = (
        '  File "/app/pkg/baz.py", line 5, in run\n    obj = <0x7f1234> at 0xdeadbeef\n'
    )
    frames = _extract_frames(tb)
    for f in frames:
        assert "0x7f1234" not in f
        assert "0xdeadbeef" not in f


@pytest.mark.unit
def test_fingerprint_preserves_frame_order() -> None:
    """Frame order encodes call stack — must be preserved, not sorted."""
    tb = """
  File "/app/pkg/a.py", line 1, in outer
  File "/app/pkg/b.py", line 2, in inner
"""
    frames = _extract_frames(tb)
    assert frames == ["pkg/a.py:outer", "pkg/b.py:inner"]
    # Reversed order must produce different fingerprint
    fp1 = compute_error_fingerprint(failure_output=tb, failing_tests=[])
    tb_reversed = """
  File "/app/pkg/b.py", line 2, in inner
  File "/app/pkg/a.py", line 1, in outer
"""
    fp2 = compute_error_fingerprint(failure_output=tb_reversed, failing_tests=[])
    assert fp1 != fp2


@pytest.mark.unit
def test_fingerprint_sorts_failing_tests() -> None:
    """Failing test names are order-independent — same set = same fingerprint."""
    fp1 = compute_error_fingerprint(
        failure_output="", failing_tests=["test_b", "test_a"]
    )
    fp2 = compute_error_fingerprint(
        failure_output="", failing_tests=["test_a", "test_b"]
    )
    assert fp1 == fp2
