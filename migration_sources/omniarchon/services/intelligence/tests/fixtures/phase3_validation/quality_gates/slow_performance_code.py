"""
Slow Performance Code Fixture

This fixture provides code with performance issues for testing
performance quality gates.

Performance Issues:
- Inefficient algorithms (O(n²) where O(n) possible)
- N+1 query patterns
- Memory leaks
- Unnecessary loops
- Missing caching
- Blocking operations
"""

import time
from typing import Any, Dict, List, Optional

# ============================================================================
# INEFFICIENT ALGORITHM: O(n²)
# ============================================================================


class ListProcessor:
    """List processing with inefficient algorithms."""

    def find_duplicates(self, items: List[int]) -> List[int]:
        """
        Find duplicates using O(n²) algorithm.

        PERFORMANCE ISSUE: O(n²) complexity
        SHOULD BE: O(n) using set
        """
        duplicates = []

        # O(n²) nested loop
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i] == items[j] and items[i] not in duplicates:
                    duplicates.append(items[i])

        return duplicates

    def find_common_elements(self, list1: List[int], list2: List[int]) -> List[int]:
        """
        Find common elements using O(n*m) algorithm.

        PERFORMANCE ISSUE: O(n*m) complexity
        SHOULD BE: O(n+m) using set intersection
        """
        common = []

        # O(n*m) nested loop
        for item1 in list1:
            for item2 in list2:
                if item1 == item2 and item1 not in common:
                    common.append(item1)

        return common


# ============================================================================
# N+1 QUERY PATTERN
# ============================================================================


class UserRepository:
    """User repository with N+1 query anti-pattern."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def get_users_with_orders(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get users with their orders using N+1 queries.

        PERFORMANCE ISSUE: N+1 queries
        SHOULD BE: 2 queries total (1 for users, 1 for all orders)
        """
        users = []

        # Query 1: Get all users (good)
        for user_id in user_ids:
            user = await self._get_user(user_id)  # N queries

            # Query N+1: Get orders for each user individually (BAD)
            user["orders"] = await self._get_user_orders(user_id)  # N more queries

            users.append(user)

        return users

    async def _get_user(self, user_id: int) -> Dict[str, Any]:
        """Simulated user query."""
        time.sleep(0.01)  # Simulate database query
        return {"id": user_id, "name": f"User {user_id}"}

    async def _get_user_orders(self, user_id: int) -> List[Dict[str, Any]]:
        """Simulated orders query."""
        time.sleep(0.01)  # Simulate database query
        return [{"id": 1, "user_id": user_id, "total": 100}]


# ============================================================================
# MEMORY LEAK
# ============================================================================


class DataCache:
    """Data cache with memory leak."""

    def __init__(self):
        self._cache = {}  # Never cleaned up
        self._access_log = []  # Grows indefinitely

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        PERFORMANCE ISSUE: _access_log grows forever
        SHOULD BE: Implement size limit or TTL
        """
        # Memory leak: Appending to list that never gets cleaned
        self._access_log.append({"key": key, "timestamp": time.time()})

        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Set cached value.

        PERFORMANCE ISSUE: Cache never evicts old entries
        SHOULD BE: Implement LRU or size limit
        """
        # Memory leak: Cache grows indefinitely
        self._cache[key] = value

        # Memory leak: Another list that grows forever
        self._access_log.append({"key": key, "timestamp": time.time(), "action": "set"})


# ============================================================================
# UNNECESSARY LOOPS
# ============================================================================


class StringProcessor:
    """String processing with unnecessary loops."""

    def process_strings(self, strings: List[str]) -> List[str]:
        """
        Process strings with multiple unnecessary passes.

        PERFORMANCE ISSUE: Multiple passes over data
        SHOULD BE: Single pass
        """
        # Pass 1: Strip whitespace
        stripped = []
        for s in strings:
            stripped.append(s.strip())

        # Pass 2: Convert to lowercase (could be done in Pass 1)
        lowercased = []
        for s in stripped:
            lowercased.append(s.lower())

        # Pass 3: Remove duplicates (could be done in Pass 1)
        unique = []
        for s in lowercased:
            if s not in unique:
                unique.append(s)

        # Pass 4: Sort (could be done more efficiently)
        sorted_list = []
        for s in sorted(unique):
            sorted_list.append(s)

        return sorted_list


# ============================================================================
# MISSING CACHING
# ============================================================================


class ExpensiveCalculator:
    """Calculator without caching for expensive operations."""

    def fibonacci(self, n: int) -> int:
        """
        Calculate Fibonacci number without caching.

        PERFORMANCE ISSUE: Exponential time O(2^n)
        SHOULD BE: Use memoization for O(n)
        """
        if n <= 1:
            return n

        # Recalculates same values many times
        return self.fibonacci(n - 1) + self.fibonacci(n - 2)

    def factorial(self, n: int) -> int:
        """
        Calculate factorial without caching.

        PERFORMANCE ISSUE: Recalculates unnecessarily
        SHOULD BE: Use cache for frequently calculated values
        """
        if n <= 1:
            return 1

        return n * self.factorial(n - 1)


# ============================================================================
# BLOCKING OPERATIONS
# ============================================================================


class FileProcessor:
    """File processor with blocking operations."""

    def process_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Process files synchronously.

        PERFORMANCE ISSUE: Sequential blocking I/O
        SHOULD BE: Use async I/O or parallel processing
        """
        results = []

        for file_path in file_paths:
            # Blocking file read
            content = self._read_file_blocking(file_path)

            # Blocking processing
            processed = self._process_content_blocking(content)

            # Blocking write
            self._write_result_blocking(file_path, processed)

            results.append({"file": file_path, "status": "processed"})

        return results

    def _read_file_blocking(self, path: str) -> str:
        """Blocking file read."""
        time.sleep(0.1)  # Simulate slow I/O
        return "file content"

    def _process_content_blocking(self, content: str) -> str:
        """Blocking processing."""
        time.sleep(0.1)  # Simulate slow processing
        return content.upper()

    def _write_result_blocking(self, path: str, content: str) -> None:
        """Blocking file write."""
        time.sleep(0.1)  # Simulate slow I/O


# ============================================================================
# INEFFICIENT DATA STRUCTURES
# ============================================================================


class SetOperations:
    """Set operations using wrong data structures."""

    def check_membership(
        self, items: List[int], search_values: List[int]
    ) -> List[bool]:
        """
        Check membership using list instead of set.

        PERFORMANCE ISSUE: O(n*m) for list membership
        SHOULD BE: O(n+m) using set
        """
        results = []

        for value in search_values:
            # O(n) membership check for each value
            results.append(value in items)

        return results

    def remove_duplicates(self, items: List[int]) -> List[int]:
        """
        Remove duplicates using list operations.

        PERFORMANCE ISSUE: O(n²) duplicate checking
        SHOULD BE: O(n) using set
        """
        unique = []

        for item in items:
            # O(n) membership check
            if item not in unique:
                unique.append(item)

        return unique


# ============================================================================
# STRING CONCATENATION IN LOOP
# ============================================================================


class ReportGenerator:
    """Report generator with inefficient string building."""

    def generate_report(self, data: List[Dict[str, Any]]) -> str:
        """
        Generate report using string concatenation.

        PERFORMANCE ISSUE: O(n²) string concatenation
        SHOULD BE: Use list append + join for O(n)
        """
        report = ""  # String concatenation in loop is inefficient

        for item in data:
            # Each concatenation creates new string object
            report += f"Item: {item['name']}\n"
            report += f"Value: {item['value']}\n"
            report += f"Status: {item['status']}\n"
            report += "---\n"

        return report


# ============================================================================
# Performance Metrics
# ============================================================================

PERFORMANCE_METRICS = {
    "ListProcessor.find_duplicates": {
        "time_complexity": "O(n²)",
        "should_be": "O(n)",
        "execution_time_ms": 1500,  # For n=1000
        "sla_ms": 100,
        "violations": ["time_complexity", "sla"],
    },
    "UserRepository.get_users_with_orders": {
        "query_count": 201,  # N+1 for 100 users
        "should_be": 2,
        "execution_time_ms": 2010,
        "sla_ms": 100,
        "violations": ["n_plus_1", "sla"],
    },
    "DataCache": {
        "memory_leak": True,
        "memory_growth_per_operation_kb": 1.2,
        "operations_until_oom": 100000,
        "violations": ["memory_leak", "unbounded_growth"],
    },
    "ExpensiveCalculator.fibonacci": {
        "time_complexity": "O(2^n)",
        "should_be": "O(n)",
        "execution_time_ms": 5000,  # For n=30
        "sla_ms": 10,
        "violations": ["exponential_time", "sla"],
    },
    "FileProcessor.process_files": {
        "parallelization": False,
        "execution_time_ms": 3000,  # For 10 files
        "parallel_time_ms": 300,  # What it could be
        "violations": ["blocking_io", "no_parallelization"],
    },
    "ReportGenerator.generate_report": {
        "time_complexity": "O(n²)",
        "should_be": "O(n)",
        "execution_time_ms": 800,  # For n=1000
        "sla_ms": 100,
        "violations": ["string_concatenation", "sla"],
    },
}


# ============================================================================
# Performance SLA Violations
# ============================================================================

SLA_VIOLATIONS = {
    "operation": "ListProcessor.find_duplicates",
    "sla_requirement": "< 100ms for 1000 items",
    "actual_performance": "1500ms for 1000 items",
    "violation_factor": 15.0,  # 15x slower than SLA
    "recommended_fix": "Use set for O(n) complexity",
}
