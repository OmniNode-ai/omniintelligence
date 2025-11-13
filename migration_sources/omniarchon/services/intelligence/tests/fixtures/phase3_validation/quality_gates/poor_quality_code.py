"""
Poor Quality Code Fixture

This fixture provides code with quality issues for testing
quality gate validation.

Quality Issues:
- High cyclomatic complexity
- Code duplication
- Long methods
- Deep nesting
- Poor naming
- Missing documentation
- Anti-patterns
"""

from typing import Any, Dict, List

# ============================================================================
# HIGH COMPLEXITY: Cyclomatic Complexity > 10
# ============================================================================


class OrderProcessor:
    """Order processing with high complexity."""

    def process_order(  # Cyclomatic Complexity: 15
        self, order: Dict[str, Any], user: Dict[str, Any], inventory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process order with excessive branching and complexity.

        QUALITY ISSUES:
        - Complexity: 15 (threshold: 10)
        - Nesting depth: 5 (threshold: 3)
        - Method length: 80 lines (threshold: 50)
        """
        result = {"status": "pending"}

        # Branch 1-3
        if not order:
            return {"status": "error", "message": "No order"}
        elif not user:
            return {"status": "error", "message": "No user"}
        elif not inventory:
            return {"status": "error", "message": "No inventory"}

        # Branch 4-7
        if order.get("type") == "standard":
            if user.get("membership") == "premium":
                if order.get("total") > 100:
                    if inventory.get("stock") > 0:
                        result["discount"] = 0.2
                        result["shipping"] = "free"
                    else:
                        return {"status": "error", "message": "Out of stock"}
                else:
                    result["discount"] = 0.1
            else:
                if order.get("total") > 50:
                    result["discount"] = 0.05
        # Branch 8-12
        elif order.get("type") == "express":
            if user.get("membership") == "premium":
                if order.get("total") > 200:
                    if inventory.get("express_stock") > 0:
                        if user.get("credits") > 10:
                            result["discount"] = 0.25
                            result["shipping"] = "free"
                            result["credits_used"] = 10
                        else:
                            result["discount"] = 0.15
                    else:
                        return {"status": "error", "message": "No express stock"}
                else:
                    result["discount"] = 0.1
            else:
                result["shipping_fee"] = 15
        # Branch 13-15
        elif order.get("type") == "international":
            if user.get("verified"):
                if order.get("total") > 500:
                    result["customs_fee"] = order["total"] * 0.1
                else:
                    result["customs_fee"] = 25
            else:
                return {"status": "error", "message": "User not verified"}

        result["status"] = "processed"
        return result


# ============================================================================
# CODE DUPLICATION
# ============================================================================


class UserManager:
    """User management with extensive code duplication."""

    def create_admin_user(self, name: str, email: str) -> Dict[str, Any]:
        """Create admin user with duplicated logic."""
        # DUPLICATION: Same validation as create_regular_user
        if not name:
            return {"error": "Name required"}
        if len(name) < 3:
            return {"error": "Name too short"}
        if not email:
            return {"error": "Email required"}
        if "@" not in email:
            return {"error": "Invalid email"}

        # DUPLICATION: Same user creation as create_regular_user
        user = {
            "name": name,
            "email": email,
            "role": "admin",
            "created_at": "2025-01-01",
            "active": True,
        }

        return {"success": True, "user": user}

    def create_regular_user(self, name: str, email: str) -> Dict[str, Any]:
        """Create regular user with duplicated logic."""
        # DUPLICATION: Exact same validation as create_admin_user
        if not name:
            return {"error": "Name required"}
        if len(name) < 3:
            return {"error": "Name too short"}
        if not email:
            return {"error": "Email required"}
        if "@" not in email:
            return {"error": "Invalid email"}

        # DUPLICATION: Same user creation as create_admin_user
        user = {
            "name": name,
            "email": email,
            "role": "user",
            "created_at": "2025-01-01",
            "active": True,
        }

        return {"success": True, "user": user}

    def create_guest_user(self, name: str, email: str) -> Dict[str, Any]:
        """Create guest user with duplicated logic."""
        # DUPLICATION: Same validation again
        if not name:
            return {"error": "Name required"}
        if len(name) < 3:
            return {"error": "Name too short"}
        if not email:
            return {"error": "Email required"}
        if "@" not in email:
            return {"error": "Invalid email"}

        # DUPLICATION: Same user creation again
        user = {
            "name": name,
            "email": email,
            "role": "guest",
            "created_at": "2025-01-01",
            "active": True,
        }

        return {"success": True, "user": user}


# ============================================================================
# LONG METHOD: >50 lines
# ============================================================================


class DataAnalyzer:
    """Data analysis with overly long methods."""

    def analyze_dataset(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze dataset with overly long method.

        QUALITY ISSUES:
        - Method length: 70 lines (threshold: 50)
        - Multiple responsibilities (SRP violation)
        - Should be split into smaller methods
        """
        # Initialize results
        results = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "statistics": {},
            "anomalies": [],
            "trends": [],
        }

        # Count records
        results["total_records"] = len(dataset)

        # Validate records
        valid_data = []
        for record in dataset:
            if self._is_valid_record(record):
                valid_data.append(record)
                results["valid_records"] += 1
            else:
                results["invalid_records"] += 1

        # Calculate basic statistics
        if valid_data:
            values = [r.get("value", 0) for r in valid_data]
            results["statistics"]["mean"] = sum(values) / len(values)
            results["statistics"]["min"] = min(values)
            results["statistics"]["max"] = max(values)
            results["statistics"]["median"] = sorted(values)[len(values) // 2]

        # Detect anomalies
        mean = results["statistics"].get("mean", 0)
        for record in valid_data:
            value = record.get("value", 0)
            if abs(value - mean) > mean * 2:
                results["anomalies"].append(record)

        # Analyze trends
        if len(valid_data) > 1:
            for i in range(len(valid_data) - 1):
                current = valid_data[i].get("value", 0)
                next_val = valid_data[i + 1].get("value", 0)
                if next_val > current:
                    trend = "increasing"
                elif next_val < current:
                    trend = "decreasing"
                else:
                    trend = "stable"
                results["trends"].append(trend)

        # Calculate percentiles
        if valid_data:
            values = sorted([r.get("value", 0) for r in valid_data])
            results["statistics"]["p25"] = values[len(values) // 4]
            results["statistics"]["p50"] = values[len(values) // 2]
            results["statistics"]["p75"] = values[(len(values) * 3) // 4]
            results["statistics"]["p90"] = values[(len(values) * 9) // 10]

        return results

    def _is_valid_record(self, record: Dict[str, Any]) -> bool:
        """Check if record is valid."""
        return "value" in record and isinstance(record["value"], (int, float))


# ============================================================================
# POOR NAMING
# ============================================================================


class d:  # POOR: Single letter class name
    """Data processor with poor naming."""

    def p(self, x: Any) -> Any:  # POOR: Single letter method/parameter
        """Process data."""
        y = x * 2  # POOR: Single letter variable
        z = y + 10  # POOR: Single letter variable
        return z

    def calc(self, data: List[int]) -> int:  # POOR: Abbreviated name
        """Calculate something."""
        temp = 0  # POOR: Generic name
        for item in data:
            temp += item
        return temp

    def do_stuff(self, a, b, c):  # POOR: Vague method name and parameters
        """Do something."""
        result = a + b * c
        return result


# ============================================================================
# MISSING DOCUMENTATION
# ============================================================================


class PaymentProcessor:
    """Payment processing with missing documentation."""

    def process_payment(self, amount, card, user):  # No docstring
        # No comments explaining logic
        if amount > 0:
            if card:
                if user:
                    # Complex business logic with no explanation
                    fee = amount * 0.029 + 0.30
                    total = amount + fee
                    return {"total": total, "fee": fee}
        return None

    def refund(self, transaction_id):  # No docstring
        pass  # No implementation or comment

    def validate_card(self, card_number):  # No docstring
        return len(str(card_number)) == 16  # No explanation


# ============================================================================
# ANTI-PATTERNS
# ============================================================================


class AntiPatternExamples:
    """Examples of common anti-patterns."""

    def god_object_method(self, data):
        """God object anti-pattern - does everything."""
        # Validation
        if not data:
            return None

        # Database operations
        self._save_to_db(data)

        # Business logic
        processed = self._process(data)

        # HTTP calls
        self._send_to_api(processed)

        # File I/O
        self._write_to_file(processed)

        # Email
        self._send_email(processed)

        return processed

    def magic_numbers(self, value):
        """Magic numbers anti-pattern."""
        if value > 100:  # What is 100?
            return value * 0.85  # What is 0.85?
        elif value > 50:  # What is 50?
            return value * 0.95  # What is 0.95?
        return value

    def _save_to_db(self, data):
        pass

    def _process(self, data):
        return data

    def _send_to_api(self, data):
        pass

    def _write_to_file(self, data):
        pass

    def _send_email(self, data):
        pass


# ============================================================================
# Quality Metrics
# ============================================================================

QUALITY_METRICS = {
    "OrderProcessor.process_order": {
        "cyclomatic_complexity": 15,
        "nesting_depth": 5,
        "method_length": 80,
        "threshold_violations": ["complexity", "nesting", "length"],
    },
    "UserManager": {
        "code_duplication": 75.0,  # 75% duplicated code
        "duplication_violations": 3,  # 3 nearly identical methods
    },
    "DataAnalyzer.analyze_dataset": {
        "method_length": 70,
        "responsibilities": 5,  # Should be 1
        "threshold_violations": ["length", "srp"],
    },
    "class d": {
        "naming_violations": ["class_name", "method_names", "variable_names"],
        "average_name_length": 1.5,  # Way too short
    },
    "PaymentProcessor": {
        "missing_docstrings": 3,
        "missing_type_hints": 6,
        "code_comments": 0,
    },
    "AntiPatternExamples": {
        "anti_patterns": ["god_object", "magic_numbers", "tight_coupling"],
    },
}
