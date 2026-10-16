# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for CI fingerprint handler.

Ticket: OMN-3556
"""

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_ci_fingerprint_compute.handlers import (
    handler_fingerprint,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.handlers.handler_fingerprint import (
    _extract_frames,
    compute_error_fingerprint,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.models.model_input import (
    ModelCiFingerprintInput,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.models.model_output import (
    ModelCiFingerprintOutput,
)

FINGERPRINT_CASES = [
    {"case": "empty", "input": {"failure_output": "", "failing_tests": []}},
    {
        "case": "no_frames",
        "input": {
            "failure_output": "AssertionError: failed at 0xdeadbeef",
            "failing_tests": ["tests/test_b.py::test_b", "tests/test_a.py::test_a"],
        },
    },
    {
        "case": "stack",
        "input": {
            "failure_output": '  File "/app/pkg_a/foo.py", line 42, in outer\n  File "/app/pkg_b/foo.py", line 17, in inner\n',
            "failing_tests": ["test_b", "test_a"],
        },
    },
    {
        "case": "reversed_stack",
        "input": {
            "failure_output": '  File "/app/pkg_b/foo.py", line 17, in inner\n  File "/app/pkg_a/foo.py", line 42, in outer\n',
            "failing_tests": ["test_a", "test_b"],
        },
    },
    {
        "case": "windows",
        "input": {
            "failure_output": '  File "C:\\app\\pkg\\foo.py", line 9, in run\n<Thing at 0xF0Ac>\n',
            "failing_tests": ["test_repeat", "test_repeat"],
        },
    },
    {
        "case": "basename",
        "input": {
            "failure_output": '  File "worker.py", line 1, in main\n',
            "failing_tests": [],
        },
    },
    {
        "case": "unicode",
        "input": {
            "failure_output": '  File "/app/paquete/café.py", line 5, in ejecutar\nError: λ\n',
            "failing_tests": ["test_λ"],
        },
    },
]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("payload", FINGERPRINT_CASES, ids=lambda p: p["case"])
async def test_canonical_dispatch_matches_preserved_core(
    payload: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the production bridge against the git-preserved algorithm."""
    handler_class = getattr(handler_fingerprint, "HandlerCiFingerprint", None)
    assert handler_class is not None, (
        "contract handler must expose canonical handle(request)"
    )
    request = ModelCiFingerprintInput.model_validate(payload["input"])
    # The flip gate separately re-derives these function bodies from git.
    expected = compute_error_fingerprint(
        failure_output=request.failure_output, failing_tests=request.failing_tests
    )
    result = handler_class().handle(request)
    assert isinstance(result, ModelCiFingerprintOutput)
    assert result.fingerprint == expected
    assert len(result.fingerprint) == 64

    # The production factory must reach the canonical handler via node.compute().
    from omniintelligence.runtime.dispatch_handlers import (
        create_ci_fingerprint_dispatch_handler,
    )

    calls = []
    original = handler_class.handle

    def track_handle(self, request):
        calls.append(request)
        return original(self, request)

    monkeypatch.setattr(handler_class, "handle", track_handle)
    bridge = create_ci_fingerprint_dispatch_handler(correlation_id=uuid4())
    envelope = MagicMock()
    envelope.payload = request.model_dump(mode="json")
    dispatched = json.loads(await bridge(envelope, MagicMock()))
    assert dispatched["fingerprint"] == expected
    assert calls == [request], "production bridge must invoke canonical handle(request)"


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
