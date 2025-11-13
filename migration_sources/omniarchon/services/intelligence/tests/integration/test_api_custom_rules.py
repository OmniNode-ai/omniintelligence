"""
Integration tests for Custom Rules API

Tests all 8 endpoints with realistic scenarios:
- POST /api/custom-rules/evaluate - Evaluate rules
- GET /api/custom-rules/project/{project_id}/rules - List project rules
- POST /api/custom-rules/project/{project_id}/load-config - Load rules from YAML
- POST /api/custom-rules/project/{project_id}/rule - Register custom rule
- PUT /api/custom-rules/project/{project_id}/rule/{rule_id}/enable - Enable rule
- PUT /api/custom-rules/project/{project_id}/rule/{rule_id}/disable - Disable rule
- GET /api/custom-rules/health - Health check
- DELETE /api/custom-rules/project/{project_id}/rules - Clear project rules

Phase 5B: Quality Intelligence Upgrades
Created: 2025-10-16
"""

import pytest

# Import the FastAPI app
# Pytest pythonpath is configured to '..' (parent of tests dir = /app)
from app import app
from fastapi.testclient import TestClient


def parse_response(response):
    """
    Parse API response handling both old (flat) and new (nested) formats.

    New format:
        {"status": "success", "data": {...}, "metadata": {...}}

    Old format:
        {"success": True, "project_id": "...", ...}

    Returns: (data_dict, metadata_dict, is_success)
    """
    result = response.json()

    # Check if new format (has "status" and "data" keys)
    if "status" in result and "data" in result:
        is_success = result["status"] == "success"
        data = result.get("data", {})
        metadata = result.get("metadata", {})
    else:
        # Old format - return as-is
        is_success = result.get("success", True)
        data = result
        metadata = {}

    return data, metadata, is_success


@pytest.fixture
def client():
    """Create test client for Custom Rules API"""
    return TestClient(app)


@pytest.fixture
def sample_code_good():
    """Sample code that passes most quality rules"""
    return '''
async def process_data(input_data: str) -> dict:
    """Process input data and return results."""
    try:
        if not input_data:
            raise ValueError("Input data is required")

        result = {"status": "success", "data": input_data}
        return result
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise
'''


@pytest.fixture
def sample_code_bad():
    """Sample code with multiple quality violations"""
    return """
def process_data(input_data):
    print("Processing data:", input_data)

    global_var = "test"

    if input_data:
        if len(input_data) > 0:
            if input_data != "":
                if input_data.strip():
                    if not input_data.isspace():
                        if input_data[0].isalpha():
                            if len(input_data) < 100:
                                if input_data.count(" ") < 10:
                                    return input_data
    return None
"""


@pytest.fixture
def sample_code_onex_node():
    """Sample ONEX node code"""
    return '''
class NodeValidationEffect(NodeBase):
    """Effect node for validation."""

    async def execute_effect(self, contract: Contract) -> dict:
        """Execute validation effect with input checks."""
        try:
            validated_data = self.validate_input(contract.payload)
            result = await self._process_validation(validated_data)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise

    def validate_input(self, data: dict) -> dict:
        """Validate input data structure."""
        if not data:
            raise ValueError("Data is required")
        return data
'''


@pytest.fixture
def config_path():
    """Path to test configuration file"""
    return "test_project.yaml"


@pytest.fixture
def security_config_path():
    """Path to security configuration file"""
    return "security_project.yaml"


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesEvaluationAPI:
    """Test rule evaluation endpoint"""

    def test_evaluate_good_code(self, client, sample_code_good):
        """Test evaluation with high-quality code"""
        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": "test_project_eval",
                "code": sample_code_good,
                "file_path": "src/processor.py",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        assert is_success
        project_id = metadata.get("project_id", data.get("project_id"))
        file_path = metadata.get("file_path", data.get("file_path"))
        assert project_id == "test_project_eval"
        assert file_path == "src/processor.py"
        assert "custom_score" in data
        assert "violations" in data
        assert "warnings" in data
        assert "suggestions" in data
        assert "rules_evaluated" in data

        # With no rules registered, score should be 1.0
        assert data["custom_score"] == 1.0
        assert len(data["violations"]) == 0

    def test_evaluate_bad_code(self, client, sample_code_bad):
        """Test evaluation with low-quality code"""
        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": "test_project_eval",
                "code": sample_code_bad,
                "file_path": "src/bad_code.py",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        # With no rules, even bad code gets perfect score
        assert data["custom_score"] == 1.0

    def test_evaluate_with_loaded_rules(self, client, config_path, sample_code_bad):
        """Test evaluation after loading rules from config"""
        project_id = "test_project_with_rules"

        # Load rules first
        load_response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )
        assert load_response.status_code == 200

        # Evaluate code
        eval_response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": sample_code_bad,
                "file_path": "src/bad_code.py",
            },
        )

        assert eval_response.status_code == 200
        data = eval_response.json()

        # Bad code should have low score with rules enabled
        assert data["custom_score"] < 0.8
        assert data["rules_evaluated"] > 0

        # Should have violations/warnings
        assert len(data["violations"]) + len(data["warnings"]) > 0

    def test_evaluate_onex_node(self, client, config_path, sample_code_onex_node):
        """Test evaluation of ONEX-compliant node"""
        project_id = "test_onex_project"

        # Load rules
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )

        # Evaluate ONEX node
        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": sample_code_onex_node,
                "file_path": "src/nodes/validation_effect.py",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        # ONEX node should have high score
        assert data["custom_score"] >= 0.7

        # Should pass architectural rules (NodeBase inheritance, async execute_effect)
        critical_violations = [
            v for v in data["violations"] if v["severity"] == "critical"
        ]
        assert len(critical_violations) == 0

    def test_evaluate_invalid_code(self, client):
        """Test evaluation with syntactically invalid code"""
        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": "test_invalid",
                "code": "def invalid syntax here",
                "file_path": "src/invalid.py",
            },
        )

        # Should still return success (rules handle syntax errors gracefully)
        assert response.status_code == 200

    def test_evaluate_missing_fields(self, client):
        """Test evaluation with missing required fields"""
        response = client.post(
            "/api/custom-rules/evaluate",
            json={"project_id": "test"},  # Missing code field
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesConfigurationAPI:
    """Test configuration loading and rule management"""

    def test_load_config_success(self, client, config_path):
        """Test successful YAML configuration loading"""
        project_id = "test_config_load"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        # Verify response structure
        assert metadata.get("project_id", data.get("project_id")) == project_id
        assert "config_path" in data
        assert "rules_loaded" in data
        assert "rule_ids" in data

        # Verify rules were loaded
        assert data["rules_loaded"] > 0
        assert len(data["rule_ids"]) == data["rules_loaded"]

        # Verify expected rule IDs
        expected_rules = [
            "no_print_statements",
            "require_type_hints",
            "max_function_complexity",
            "docstring_coverage",
            "require_node_base",
        ]
        for rule_id in expected_rules:
            assert rule_id in data["rule_ids"]

    def test_load_config_path_traversal_protection(self, client):
        """Test path traversal attack prevention"""
        project_id = "test_security"

        # Attempt path traversal
        response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": "../../etc/passwd"},
        )

        # Should be rejected
        assert response.status_code == 400
        assert "Configuration path must be within" in response.json()["detail"]

    def test_load_config_path_traversal_variants(self, client):
        """Test various path traversal attack patterns"""
        project_id = "test_security_variants"

        attack_patterns = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "./../../secrets.yaml",
            "../../../../../../root/.ssh/id_rsa",
        ]

        for pattern in attack_patterns:
            response = client.post(
                f"/api/custom-rules/project/{project_id}/load-config",
                json={"config_path": pattern},
            )

            # All should be rejected
            assert response.status_code in [
                400,
                404,
            ], f"Path traversal not blocked: {pattern}"

    def test_load_config_nonexistent_file(self, client):
        """Test loading from non-existent file"""
        project_id = "test_nonexistent"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": "nonexistent_config.yaml"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_load_multiple_configs(self, client, config_path, security_config_path):
        """Test loading multiple configurations for different projects"""
        # Load config for first project
        response1 = client.post(
            "/api/custom-rules/project/project_alpha/load-config",
            json={"config_path": config_path},
        )
        assert response1.status_code == 200
        rules_count_1 = response1.json()["rules_loaded"]

        # Load config for second project
        response2 = client.post(
            "/api/custom-rules/project/project_beta/load-config",
            json={"config_path": security_config_path},
        )
        assert response2.status_code == 200
        rules_count_2 = response2.json()["rules_loaded"]

        # Different projects should have different rule counts
        assert rules_count_1 != rules_count_2


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesRegistrationAPI:
    """Test dynamic rule registration"""

    def test_register_pattern_rule(self, client):
        """Test registering a pattern-based rule"""
        project_id = "test_register"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/rule",
            json={
                "rule_id": "custom_pattern_rule",
                "rule_type": "pattern",
                "description": "Custom pattern validation",
                "severity": "warning",
                "weight": 0.15,
                "enabled": True,
                "pattern": r"TODO|FIXME",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert metadata.get("project_id", data.get("project_id")) == project_id
        assert data["rule_id"] == "custom_pattern_rule"
        assert "registered successfully" in data["message"]

    def test_register_metric_rule(self, client):
        """Test registering a metric-based rule"""
        project_id = "test_register_metric"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/rule",
            json={
                "rule_id": "max_complexity_5",
                "rule_type": "metric",
                "description": "Maximum complexity of 5",
                "severity": "critical",
                "weight": 0.3,
                "enabled": True,
                "max_complexity": 5,
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["rule_id"] == "max_complexity_5"

    def test_register_architectural_rule(self, client):
        """Test registering an architectural rule"""
        project_id = "test_register_arch"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/rule",
            json={
                "rule_id": "require_base_class",
                "rule_type": "architectural",
                "description": "Must inherit from BaseService",
                "severity": "critical",
                "weight": 0.25,
                "enabled": True,
                "requires": "BaseService",
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_register_forbid_pattern_rule(self, client):
        """Test registering a pattern forbidding rule"""
        project_id = "test_register_forbid"

        response = client.post(
            f"/api/custom-rules/project/{project_id}/rule",
            json={
                "rule_id": "no_eval_usage",
                "rule_type": "pattern",
                "description": "Forbid eval() usage",
                "severity": "critical",
                "weight": 0.3,
                "enabled": True,
                "forbids": r"eval\s*\(",
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesListAPI:
    """Test rule listing endpoint"""

    def test_list_empty_project_rules(self, client):
        """Test listing rules for project with no rules"""
        response = client.get("/api/custom-rules/project/empty_project/rules")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert metadata.get("project_id", data.get("project_id")) == "empty_project"
        assert data["rules_count"] == 0
        assert len(data["rules"]) == 0

    def test_list_project_rules_after_load(self, client, config_path):
        """Test listing rules after loading configuration"""
        project_id = "test_list_rules"

        # Load config
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )

        # List rules
        response = client.get(f"/api/custom-rules/project/{project_id}/rules")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["rules_count"] > 0
        assert len(data["rules"]) == data["rules_count"]

        # Verify rule structure
        for rule in data["rules"]:
            assert "rule_id" in rule
            assert "rule_type" in rule
            assert "description" in rule
            assert "severity" in rule
            assert "weight" in rule
            assert "enabled" in rule
            assert rule["rule_type"] in ["pattern", "metric", "architectural"]
            assert rule["severity"] in ["critical", "warning", "suggestion"]

    def test_list_rules_after_registration(self, client):
        """Test listing rules after dynamic registration"""
        project_id = "test_list_dynamic"

        # Register multiple rules
        rules = [
            {"rule_id": "rule_1", "rule_type": "pattern", "pattern": r"test"},
            {"rule_id": "rule_2", "rule_type": "metric", "max_complexity": 10},
            {"rule_id": "rule_3", "rule_type": "architectural", "requires": "Base"},
        ]

        for rule_data in rules:
            rule_data.update(
                {
                    "description": "Test rule",
                    "severity": "warning",
                    "weight": 0.1,
                    "enabled": True,
                }
            )
            client.post(f"/api/custom-rules/project/{project_id}/rule", json=rule_data)

        # List rules
        response = client.get(f"/api/custom-rules/project/{project_id}/rules")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["rules_count"] == 3
        rule_ids = [r["rule_id"] for r in data["rules"]]
        assert "rule_1" in rule_ids
        assert "rule_2" in rule_ids
        assert "rule_3" in rule_ids


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesEnableDisableAPI:
    """Test rule enable/disable functionality"""

    def test_disable_rule(self, client, config_path):
        """Test disabling a rule"""
        project_id = "test_disable"

        # Load config
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )

        # Disable rule
        response = client.put(
            f"/api/custom-rules/project/{project_id}/rule/no_print_statements/disable"
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["rule_id"] == "no_print_statements"
        assert "disabled" in data["message"]

    def test_enable_rule(self, client, config_path):
        """Test enabling a disabled rule"""
        project_id = "test_enable"

        # Load config
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )

        # Disable then enable
        client.put(
            f"/api/custom-rules/project/{project_id}/rule/max_function_complexity/disable"
        )

        response = client.put(
            f"/api/custom-rules/project/{project_id}/rule/max_function_complexity/enable"
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert "enabled" in data["message"]

    def test_disable_nonexistent_rule(self, client):
        """Test disabling a rule that doesn't exist"""
        response = client.put(
            "/api/custom-rules/project/test_project/rule/nonexistent_rule/disable"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_enable_nonexistent_rule(self, client):
        """Test enabling a rule that doesn't exist"""
        response = client.put(
            "/api/custom-rules/project/test_project/rule/nonexistent_rule/enable"
        )

        assert response.status_code == 404

    def test_rule_lifecycle(self, client, config_path, sample_code_bad):
        """Test complete rule lifecycle: load, evaluate, disable, re-evaluate"""
        project_id = "test_lifecycle"

        # Step 1: Load rules
        load_response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )
        assert load_response.status_code == 200

        # Step 2: Evaluate with all rules enabled
        eval1_response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": sample_code_bad,
                "file_path": "test.py",
            },
        )
        assert eval1_response.status_code == 200
        eval1_response.json()["custom_score"]
        rules_evaluated_1 = eval1_response.json()["rules_evaluated"]

        # Step 3: Disable some rules
        client.put(
            f"/api/custom-rules/project/{project_id}/rule/no_print_statements/disable"
        )
        client.put(
            f"/api/custom-rules/project/{project_id}/rule/max_function_complexity/disable"
        )

        # Step 4: Re-evaluate with fewer rules
        eval2_response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": sample_code_bad,
                "file_path": "test.py",
            },
        )
        assert eval2_response.status_code == 200
        eval2_response.json()["custom_score"]
        rules_evaluated_2 = eval2_response.json()["rules_evaluated"]

        # Fewer rules should be evaluated
        assert rules_evaluated_2 < rules_evaluated_1

        # Step 5: Re-enable rules
        client.put(
            f"/api/custom-rules/project/{project_id}/rule/no_print_statements/enable"
        )
        client.put(
            f"/api/custom-rules/project/{project_id}/rule/max_function_complexity/enable"
        )

        # Step 6: Verify rules are active again
        eval3_response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": sample_code_bad,
                "file_path": "test.py",
            },
        )
        assert eval3_response.status_code == 200
        rules_evaluated_3 = eval3_response.json()["rules_evaluated"]

        # Should evaluate same number as originally
        assert rules_evaluated_3 == rules_evaluated_1


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesHealthAPI:
    """Test health check endpoint"""

    def test_health_check_empty_service(self, client):
        """Test health check with no projects"""
        response = client.get("/api/custom-rules/health")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["service"] == "custom_quality_rules"
        assert data["status"] == "healthy"

        # Health check data is in "checks" sub-object
        checks = data.get("checks", data)
        assert "total_projects" in checks
        assert "total_rules" in checks
        assert checks["total_projects"] >= 0
        assert checks["total_rules"] >= 0

    def test_health_check_with_loaded_rules(self, client, config_path):
        """Test health check after loading rules"""
        # Load rules for multiple projects
        projects = ["health_test_1", "health_test_2", "health_test_3"]

        for project in projects:
            client.post(
                f"/api/custom-rules/project/{project}/load-config",
                json={"config_path": config_path},
            )

        # Check health
        response = client.get("/api/custom-rules/health")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["status"] == "healthy"

        # Health check data is in "checks" sub-object
        checks = data.get("checks", data)
        assert checks.get("total_projects", data.get("total_projects")) >= 3
        assert checks.get("total_rules", data.get("total_rules")) > 0


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesClearAPI:
    """Test clearing project rules"""

    def test_clear_project_rules(self, client, config_path):
        """Test clearing all rules for a project"""
        project_id = "test_clear"

        # Load rules
        load_response = client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": config_path},
        )
        rules_loaded = load_response.json()["rules_loaded"]

        # Clear rules
        response = client.delete(f"/api/custom-rules/project/{project_id}/rules")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert metadata.get("project_id", data.get("project_id")) == project_id
        assert data["rules_cleared"] == rules_loaded

        # Verify rules are cleared
        list_response = client.get(f"/api/custom-rules/project/{project_id}/rules")
        assert list_response.json()["rules_count"] == 0

    def test_clear_nonexistent_project(self, client):
        """Test clearing rules for project with no rules"""
        response = client.delete("/api/custom-rules/project/nonexistent_project/rules")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        assert data["rules_cleared"] == 0


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesSecurityScenarios:
    """Test security-focused scenarios"""

    def test_security_rules_evaluation(self, client, security_config_path):
        """Test evaluation with security-focused rules"""
        project_id = "security_test"

        # Load security rules
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": security_config_path},
        )

        # Code with security issues
        insecure_code = """
def login(username, password):
    # Hardcoded password - BAD!
    admin_password = "SuperSecret123"

    # SQL injection risk - BAD!
    query = f"SELECT * FROM users WHERE username='{username}'"
    db.execute(query)

    return True
"""

        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": insecure_code,
                "file_path": "src/auth.py",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        # Should have critical violations
        critical_violations = [
            v for v in data["violations"] if v["severity"] == "critical"
        ]
        assert len(critical_violations) > 0

        # Score should be low
        assert data["custom_score"] < 0.6

    def test_secure_code_passes(self, client, security_config_path):
        """Test that secure code passes security rules"""
        project_id = "security_pass"

        # Load security rules
        client.post(
            f"/api/custom-rules/project/{project_id}/load-config",
            json={"config_path": security_config_path},
        )

        # Secure code
        secure_code = '''
def login(username: str, password: str) -> bool:
    """Secure login implementation."""
    try:
        # Input validation
        validated_username = sanitize_input(username)
        validated_password = validate_password(password)

        # Parameterized query
        query = "SELECT * FROM users WHERE username = ?"
        result = db.execute(query, (validated_username,))

        return verify_credentials(result, validated_password)
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False
'''

        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": project_id,
                "code": secure_code,
                "file_path": "src/auth_secure.py",
            },
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert is_success

        # Should have no critical violations
        critical_violations = [
            v for v in data["violations"] if v["severity"] == "critical"
        ]
        assert len(critical_violations) == 0

        # Score should be high
        assert data["custom_score"] >= 0.7


@pytest.mark.integration
@pytest.mark.custom_rules
class TestCustomRulesEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_code_evaluation(self, client):
        """Test evaluating empty code"""
        response = client.post(
            "/api/custom-rules/evaluate",
            json={"project_id": "test_empty", "code": "", "file_path": "empty.py"},
        )

        # Should handle gracefully
        assert response.status_code == 200

    def test_very_large_code_evaluation(self, client):
        """Test evaluating very large code file"""
        # Generate large code (but under 1MB limit)
        large_code = "def function_" + "\n".join([f"x_{i} = {i}" for i in range(10000)])

        response = client.post(
            "/api/custom-rules/evaluate",
            json={
                "project_id": "test_large",
                "code": large_code,
                "file_path": "large.py",
            },
        )

        # Should handle gracefully
        assert response.status_code == 200

    def test_code_exceeding_size_limit(self, client):
        """Test code exceeding 1MB limit"""
        # Generate > 1MB of code
        huge_code = "x = 1\n" * 100000

        response = client.post(
            "/api/custom-rules/evaluate",
            json={"project_id": "test_huge", "code": huge_code, "file_path": "huge.py"},
        )

        # Should be rejected with validation error
        assert response.status_code == 422

    def test_concurrent_rule_operations(self, client, config_path):
        """Test concurrent rule loading and evaluation"""
        import concurrent.futures

        project_ids = [f"concurrent_test_{i}" for i in range(5)]

        def load_and_evaluate(project_id):
            # Load config
            load_resp = client.post(
                f"/api/custom-rules/project/{project_id}/load-config",
                json={"config_path": config_path},
            )

            # Evaluate code
            eval_resp = client.post(
                "/api/custom-rules/evaluate",
                json={
                    "project_id": project_id,
                    "code": "def test(): pass",
                    "file_path": "test.py",
                },
            )

            return load_resp.status_code, eval_resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(load_and_evaluate, pid) for pid in project_ids]
            results = [f.result() for f in futures]

        # All operations should succeed
        assert all(load == 200 and eval == 200 for load, eval in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
