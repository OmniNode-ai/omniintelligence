"""
Low Test Coverage Module Fixture

This fixture provides code with insufficient test coverage (<90%)
for testing quality gate validation.

Coverage Scenarios:
- Untested methods
- Uncovered branches
- Missing error path testing
- Untested edge cases
"""

from typing import Any, Dict, List, Optional

# ============================================================================
# Module with Low Coverage (~40%)
# ============================================================================


class UserValidator:
    """
    User validation class with low test coverage.

    Only basic happy path is tested, many branches and error paths untested.
    """

    def validate_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate user data.

        TESTED: Basic happy path with valid data
        UNTESTED: Error cases, edge cases, validation failures
        """
        # TESTED: Happy path
        if self._is_valid_email(user_data.get("email")):
            return {"valid": True, "user": user_data}

        # UNTESTED: Error path
        return {"valid": False, "error": "Invalid email"}

    def _is_valid_email(self, email: Optional[str]) -> bool:
        """
        Check if email is valid.

        TESTED: Valid email case
        UNTESTED: None, empty string, invalid format
        """
        # TESTED: Basic validation
        if email and "@" in email:
            return True

        # UNTESTED: All error paths
        return False

    def validate_age(self, age: Optional[int]) -> bool:
        """
        Validate user age.

        COMPLETELY UNTESTED
        """
        if age is None:
            return False

        if age < 0:
            return False

        if age > 150:
            return False

        if age < 18:
            return False

        return True

    def validate_password(self, password: Optional[str]) -> Dict[str, Any]:
        """
        Validate password strength.

        COMPLETELY UNTESTED
        """
        if not password:
            return {"valid": False, "reason": "Password required"}

        if len(password) < 8:
            return {"valid": False, "reason": "Password too short"}

        if not any(c.isupper() for c in password):
            return {"valid": False, "reason": "Need uppercase"}

        if not any(c.isdigit() for c in password):
            return {"valid": False, "reason": "Need digit"}

        return {"valid": True}

    def validate_username(self, username: Optional[str]) -> bool:
        """
        Validate username format.

        COMPLETELY UNTESTED
        """
        if not username:
            return False

        if len(username) < 3:
            return False

        if len(username) > 20:
            return False

        if not username[0].isalpha():
            return False

        return True


# ============================================================================
# Module with Partial Coverage (~60%)
# ============================================================================


class DataProcessor:
    """
    Data processing class with partial coverage.

    Main methods tested, helper methods and error paths untested.
    """

    def process_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process data items.

        TESTED: Happy path with valid data
        UNTESTED: Empty list, invalid items, exceptions
        """
        # TESTED: Normal processing
        results = []
        for item in data:
            processed = self._process_item(item)
            results.append(processed)

        return results

    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process single item.

        PARTIALLY TESTED: Only happy path
        """
        # TESTED: Normal case
        if "value" in item:
            item["processed_value"] = item["value"] * 2

        # UNTESTED: Complex transformations
        if "nested" in item:
            item["flattened"] = self._flatten_nested(item["nested"])

        # UNTESTED: Error handling
        if "error" in item:
            item["error_handled"] = True

        return item

    def _flatten_nested(self, nested: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten nested structure.

        COMPLETELY UNTESTED
        """
        flattened = {}
        for key, value in nested.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    flattened[f"{key}_{nested_key}"] = nested_value
            else:
                flattened[key] = value

        return flattened


# ============================================================================
# Coverage Statistics
# ============================================================================

LOW_COVERAGE_STATS = {
    "UserValidator": {
        "total_methods": 5,
        "tested_methods": 2,
        "coverage_percent": 40.0,
        "untested_methods": ["validate_age", "validate_password", "validate_username"],
        "partially_tested": ["validate_user", "_is_valid_email"],
    },
    "DataProcessor": {
        "total_methods": 3,
        "tested_methods": 2,
        "coverage_percent": 60.0,
        "untested_methods": ["_flatten_nested"],
        "partially_tested": ["process_data", "_process_item"],
    },
    "overall": {
        "total_lines": 150,
        "covered_lines": 75,
        "coverage_percent": 50.0,
        "branch_coverage": 30.0,  # Many branches untested
        "meets_threshold": False,  # Threshold: 90%
    },
}


# ============================================================================
# Test Coverage Report (Simulated)
# ============================================================================

COVERAGE_REPORT = """
Name                          Stmts   Miss  Branch BrPart  Cover
-----------------------------------------------------------------
low_coverage_module.py          150     75      40     28    50%
  UserValidator.validate_user    10      4       4      2    60%
  UserValidator._is_valid_email   5      2       2      1    60%
  UserValidator.validate_age     10     10       4      4     0%
  UserValidator.validate_password 15     15       5      5     0%
  UserValidator.validate_username 10     10       4      4     0%
  DataProcessor.process_data     15      5       2      1    70%
  DataProcessor._process_item    20     10       8      5    50%
  DataProcessor._flatten_nested  15     15       6      6     0%
-----------------------------------------------------------------
TOTAL                           150     75      40     28    50%

FAILED: Coverage threshold not met (50% < 90% required)
"""


# ============================================================================
# Missing Tests Examples
# ============================================================================

MISSING_TESTS = {
    "UserValidator.validate_age": [
        "test_validate_age_none",
        "test_validate_age_negative",
        "test_validate_age_too_old",
        "test_validate_age_underage",
        "test_validate_age_valid",
    ],
    "UserValidator.validate_password": [
        "test_validate_password_none",
        "test_validate_password_empty",
        "test_validate_password_too_short",
        "test_validate_password_no_uppercase",
        "test_validate_password_no_digit",
        "test_validate_password_valid",
    ],
    "DataProcessor._flatten_nested": [
        "test_flatten_nested_simple",
        "test_flatten_nested_complex",
        "test_flatten_nested_empty",
        "test_flatten_nested_deep",
    ],
}
