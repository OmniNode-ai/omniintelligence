"""Performance benchmarks for log sanitizer."""

import time

import pytest
from src.server.services.log_sanitizer import LogSanitizer


class TestLogSanitizerPerformance:
    """Benchmark tests for log sanitization performance."""

    def test_sanitization_overhead_single_line(self):
        """Measure overhead for single log line sanitization."""
        sanitizer = LogSanitizer()
        test_line = "API key: sk_test_123456 user@example.com /home/user/secret.txt"

        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            sanitizer.sanitize(test_line)
        duration = time.perf_counter() - start

        avg_ms = (duration / iterations) * 1000
        print(f"\nAverage sanitization time: {avg_ms:.3f}ms per line")
        assert avg_ms < 1.0, f"Sanitization too slow: {avg_ms:.3f}ms (target: <1ms)"

    def test_sanitization_overhead_bulk(self):
        """Measure overhead for bulk log processing."""
        sanitizer = LogSanitizer()
        test_lines = [
            "No sensitive data here",
            "API key: sk_live_abcdefgh",
            "User email: user@domain.com",
            "File path: /etc/passwd",
        ] * 250  # 1000 lines total

        start = time.perf_counter()
        for line in test_lines:
            sanitizer.sanitize(line)
        duration = time.perf_counter() - start

        throughput = len(test_lines) / duration
        print(f"\nThroughput: {throughput:.0f} lines/sec")
        assert throughput > 10000, f"Throughput too low: {throughput:.0f} lines/sec"

    def test_sanitization_no_matches(self):
        """Measure performance when no patterns match (best case)."""
        sanitizer = LogSanitizer()
        clean_line = "INFO: Application started successfully on port 8080"

        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            result = sanitizer.sanitize(clean_line)
        duration = time.perf_counter() - start

        avg_ms = (duration / iterations) * 1000
        print(f"\nClean line overhead: {avg_ms:.3f}ms")
        assert avg_ms < 0.5, "Clean lines should be fastest path"
