"""
Custom Quality Rules Engine

Per-project custom quality rules configuration with YAML support.
Enables project-specific quality validation with dynamic rule registration.

Created: 2025-10-15
Purpose: MVP Phase 5B - Quality Intelligence Upgrades
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CustomQualityRule:
    """
    Custom quality rule definition.

    Supports pattern-based, metric-based, and architectural rule types.
    """

    rule_id: str
    project_id: str
    rule_type: str  # pattern, metric, architectural
    description: str
    severity: str  # critical, warning, suggestion
    checker: Callable[[str], bool]
    weight: float  # Impact on quality score (0.0-1.0)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class CustomQualityRulesEngine:
    """
    Manage and execute custom quality rules per project.

    Features:
    - Dynamic rule registration
    - YAML configuration loading
    - Weighted scoring with severity levels
    - Pattern, metric, and architectural rule types

    Design Note:
    Methods use async interface for consistency with the broader intelligence
    service API, even though current operations are synchronous (in-memory
    list/dict manipulation). This provides forward compatibility for future
    async enhancements (e.g., database persistence, external API calls) while
    maintaining a uniform interface across the service layer.
    """

    # Security: Allowed directory for rule configuration files
    ALLOWED_CONFIG_DIR = Path("/app/config/quality_rules").resolve()

    def __init__(self):
        """Initialize custom quality rules engine."""
        self.rules: Dict[str, List[CustomQualityRule]] = {}
        self.rule_checkers: Dict[str, Callable] = {}

        # Register built-in checkers
        self._register_builtin_checkers()

    def _register_builtin_checkers(self) -> None:
        """Register built-in rule checker functions."""

        # Pattern-based checkers
        self.rule_checkers["pattern_match"] = self._create_pattern_checker

        # Metric-based checkers
        self.rule_checkers["max_function_complexity"] = self._create_complexity_checker
        self.rule_checkers["max_function_length"] = self._create_length_checker
        self.rule_checkers["min_docstring_coverage"] = self._create_docstring_checker

        # Architectural checkers
        self.rule_checkers["require_inheritance"] = self._create_inheritance_checker
        self.rule_checkers["require_method"] = self._create_method_checker
        self.rule_checkers["forbid_pattern"] = self._create_forbid_pattern_checker

    async def register_rule(self, project_id: str, rule: CustomQualityRule) -> None:
        """
        Register custom rule for project.

        Args:
            project_id: Project identifier
            rule: CustomQualityRule instance
        """
        # Async interface for forward compatibility (current impl is synchronous)
        if project_id not in self.rules:
            self.rules[project_id] = []

        self.rules[project_id].append(rule)
        logger.info(
            f"Registered rule '{rule.rule_id}' for project '{project_id}' "
            f"(type: {rule.rule_type}, severity: {rule.severity})"
        )

    async def evaluate_rules(
        self, project_id: str, code: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate custom rules for code.

        Args:
            project_id: Project identifier
            code: Code content to validate
            file_path: Optional file path for context

        Returns:
            Evaluation result with violations, warnings, suggestions, and custom score
        """
        # Async interface for forward compatibility (current impl is synchronous)
        project_rules = self.rules.get(project_id, [])
        enabled_rules = [r for r in project_rules if r.enabled]

        violations = []
        warnings = []
        suggestions = []

        total_weight = 0.0
        passed_weight = 0.0

        for rule in enabled_rules:
            total_weight += rule.weight

            try:
                # Execute rule checker
                passed = rule.checker(code)

                if passed:
                    passed_weight += rule.weight
                else:
                    issue = {
                        "rule_id": rule.rule_id,
                        "description": rule.description,
                        "severity": rule.severity,
                        "rule_type": rule.rule_type,
                        "file_path": file_path,
                    }

                    # Categorize by severity
                    if rule.severity == "critical":
                        violations.append(issue)
                    elif rule.severity == "warning":
                        warnings.append(issue)
                    else:
                        suggestions.append(issue)

            except Exception as e:
                logger.error(
                    f"Rule '{rule.rule_id}' evaluation failed: {e}", exc_info=True
                )
                # Count as failed check
                continue

        # Calculate custom score (0.0-1.0)
        custom_score = passed_weight / total_weight if total_weight > 0 else 1.0

        return {
            "custom_score": custom_score,
            "violations": violations,
            "warnings": warnings,
            "suggestions": suggestions,
            "rules_evaluated": len(enabled_rules),
            "total_weight": total_weight,
            "passed_weight": passed_weight,
        }

    async def load_project_rules(
        self, project_id: str, rules_config_path: Path
    ) -> None:
        """
        Load rules from YAML configuration file.

        Args:
            project_id: Project identifier
            rules_config_path: Path to YAML configuration file

        Raises:
            ValueError: If path is outside allowed config directory
            FileNotFoundError: If config file does not exist
        """
        try:
            # Security: Treat path as relative to ALLOWED_CONFIG_DIR
            # and verify the resolved path stays within the allowed directory
            rules_config_path = (self.ALLOWED_CONFIG_DIR / rules_config_path).resolve()

            # Verify resolved path is under ALLOWED_CONFIG_DIR
            if not rules_config_path.is_relative_to(self.ALLOWED_CONFIG_DIR):
                raise ValueError(
                    f"Invalid config path - must be within {self.ALLOWED_CONFIG_DIR}. "
                    f"Attempted path: {rules_config_path}"
                )

            # Validate file exists
            if not rules_config_path.exists():
                raise FileNotFoundError(f"Config file not found: {rules_config_path}")

            with open(rules_config_path, "r") as f:
                config = yaml.safe_load(f)

            if not config or "custom_rules" not in config:
                logger.warning(f"No custom rules found in {rules_config_path}")
                return

            # Validate project_id matches
            config_project_id = config.get("project_id", project_id)
            if config_project_id != project_id:
                logger.warning(
                    f"Project ID mismatch: config has '{config_project_id}', "
                    f"expected '{project_id}'"
                )

            # Parse and create rules
            for rule_config in config["custom_rules"]:
                rule = await self._create_rule_from_config(project_id, rule_config)
                if rule:
                    await self.register_rule(project_id, rule)

            logger.info(
                f"Loaded {len(config['custom_rules'])} rules for "
                f"project '{project_id}' from {rules_config_path}"
            )

        except FileNotFoundError:
            logger.error(f"Rules config file not found: {rules_config_path}")
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
        except Exception as e:
            logger.error(f"Failed to load project rules: {e}", exc_info=True)

    async def _create_rule_from_config(
        self, project_id: str, rule_config: Dict[str, Any]
    ) -> Optional[CustomQualityRule]:
        """
        Create CustomQualityRule from configuration dictionary.

        Args:
            project_id: Project identifier
            rule_config: Rule configuration dictionary

        Returns:
            CustomQualityRule instance or None if creation fails
        """
        try:
            rule_id = rule_config["rule_id"]
            rule_type = rule_config["rule_type"]
            description = rule_config["description"]
            severity = rule_config["severity"]
            weight = rule_config.get("weight", 0.1)
            enabled = rule_config.get("enabled", True)

            # Create checker function based on rule configuration
            checker = await self._create_checker_from_config(rule_config)

            if not checker:
                logger.error(f"Failed to create checker for rule '{rule_id}'")
                return None

            return CustomQualityRule(
                rule_id=rule_id,
                project_id=project_id,
                rule_type=rule_type,
                description=description,
                severity=severity,
                checker=checker,
                weight=weight,
                enabled=enabled,
                metadata=rule_config,
            )

        except KeyError as e:
            logger.error(f"Missing required field in rule config: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create rule from config: {e}", exc_info=True)
            return None

    async def _create_checker_from_config(
        self, rule_config: Dict[str, Any]
    ) -> Optional[Callable[[str], bool]]:
        """
        Create checker function from rule configuration.

        Args:
            rule_config: Rule configuration dictionary

        Returns:
            Checker function or None if creation fails
        """
        # Async interface for forward compatibility (current impl is synchronous)
        rule_type = rule_config["rule_type"]

        # Pattern-based rules
        if rule_type == "pattern":
            if "pattern" in rule_config:
                pattern = rule_config["pattern"]
                return self._create_pattern_checker(pattern)
            elif "forbids" in rule_config:
                forbidden = rule_config["forbids"]
                return self._create_forbid_pattern_checker(forbidden)

        # Architectural rules
        elif rule_type == "architectural":
            if "pattern" in rule_config:
                pattern = rule_config["pattern"]
                return self._create_pattern_checker(pattern)
            elif "requires" in rule_config:
                required = rule_config["requires"]
                return self._create_inheritance_checker(required)
            elif "forbids" in rule_config:
                forbidden = rule_config["forbids"]
                return self._create_forbid_pattern_checker(forbidden)

        # Metric-based rules
        elif rule_type == "metric":
            if "max_complexity" in rule_config:
                threshold = rule_config["max_complexity"]
                return self._create_complexity_checker(threshold)
            elif "max_length" in rule_config:
                threshold = rule_config["max_length"]
                return self._create_length_checker(threshold)
            elif "min_docstring_coverage" in rule_config:
                threshold = rule_config["min_docstring_coverage"]
                return self._create_docstring_checker(threshold)

        logger.error(f"Unknown rule type or missing configuration: {rule_type}")
        return None

    # =========================================================================
    # Built-in Checker Factories
    # =========================================================================

    def _create_pattern_checker(self, pattern: str) -> Callable[[str], bool]:
        """Create pattern matching checker."""
        compiled_pattern = re.compile(pattern, re.MULTILINE)

        def checker(code: str) -> bool:
            return bool(compiled_pattern.search(code))

        return checker

    def _create_forbid_pattern_checker(self, pattern: str) -> Callable[[str], bool]:
        """Create pattern forbidding checker (inverse of pattern match)."""
        compiled_pattern = re.compile(pattern, re.MULTILINE)

        def checker(code: str) -> bool:
            return not bool(compiled_pattern.search(code))

        return checker

    def _create_complexity_checker(self, max_complexity: int) -> Callable[[str], bool]:
        """Create cyclomatic complexity checker."""

        def checker(code: str) -> bool:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        complexity = self._calculate_complexity(node)
                        if complexity > max_complexity:
                            return False
                return True
            except SyntaxError:
                return False

        return checker

    def _create_length_checker(self, max_length: int) -> Callable[[str], bool]:
        """Create function length checker."""

        def checker(code: str) -> bool:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        length = len(node.body)
                        if length > max_length:
                            return False
                return True
            except SyntaxError:
                return False

        return checker

    def _create_docstring_checker(self, min_coverage: float) -> Callable[[str], bool]:
        """Create docstring coverage checker."""

        def checker(code: str) -> bool:
            try:
                tree = ast.parse(code)

                total_functions = 0
                documented_functions = 0

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_functions += 1
                        if ast.get_docstring(node):
                            documented_functions += 1

                if total_functions == 0:
                    return True  # No functions to check

                coverage = documented_functions / total_functions
                return coverage >= min_coverage
            except SyntaxError:
                return False

        return checker

    def _create_inheritance_checker(self, required_base: str) -> Callable[[str], bool]:
        """Create inheritance checker."""

        def checker(code: str) -> bool:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if class inherits from required base
                        for base in node.bases:
                            base_name = self._get_name_from_node(base)
                            if required_base == base_name:
                                return True
                return False
            except SyntaxError:
                return False

        return checker

    def _create_method_checker(self, required_method: str) -> Callable[[str], bool]:
        """Create method existence checker."""

        def checker(code: str) -> bool:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        method_names = [
                            m.name for m in node.body if isinstance(m, ast.FunctionDef)
                        ]
                        if required_method in method_names:
                            return True
                return False
            except SyntaxError:
                return False

        return checker

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """
        Calculate cyclomatic complexity for function.

        Simple implementation: count decision points + 1

        TODO: Future enhancements for more accurate complexity:
        - Count elif branches separately (currently included in If)
        - Count comprehensions with conditions (ast.ListComp, ast.DictComp, ast.SetComp with if clause)
        - Count ternary expressions (ast.IfExp)
        - Count match/case statements for Python 3.10+ (ast.Match)
        """
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Decision points that increase complexity
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _get_name_from_node(self, node: ast.AST) -> str:
        """Extract name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_name_from_node(node.value)
        return ""

    async def get_project_rules(self, project_id: str) -> List[CustomQualityRule]:
        """
        Get all rules for project.

        Args:
            project_id: Project identifier

        Returns:
            List of CustomQualityRule instances
        """
        # Async interface for forward compatibility (current impl is synchronous)
        return self.rules.get(project_id, [])

    async def disable_rule(self, project_id: str, rule_id: str) -> bool:
        """
        Disable specific rule for project.

        Args:
            project_id: Project identifier
            rule_id: Rule identifier

        Returns:
            True if rule was disabled, False if not found
        """
        # Async interface for forward compatibility (current impl is synchronous)
        project_rules = self.rules.get(project_id, [])

        for rule in project_rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                logger.info(f"Disabled rule '{rule_id}' for project '{project_id}'")
                return True

        logger.warning(f"Rule '{rule_id}' not found for project '{project_id}'")
        return False

    async def enable_rule(self, project_id: str, rule_id: str) -> bool:
        """
        Enable specific rule for project.

        Args:
            project_id: Project identifier
            rule_id: Rule identifier

        Returns:
            True if rule was enabled, False if not found
        """
        # Async interface for forward compatibility (current impl is synchronous)
        project_rules = self.rules.get(project_id, [])

        for rule in project_rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                logger.info(f"Enabled rule '{rule_id}' for project '{project_id}'")
                return True

        logger.warning(f"Rule '{rule_id}' not found for project '{project_id}'")
        return False
