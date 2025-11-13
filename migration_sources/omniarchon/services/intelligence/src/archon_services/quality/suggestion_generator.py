"""
Quality Suggestion Generator

Generates actionable improvement suggestions from validation violations and quality scores.
Part of Phase 5B: Quality Intelligence Upgrades.

Created: 2025-10-15
Purpose: Intelligent suggestion generation for code quality improvement
"""

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QualitySuggestion:
    """Represents a quality improvement suggestion"""

    type: str  # architectural, quality, security, onex_compliance
    priority: int  # 1-10 (10 = highest)
    title: str
    description: str
    code_example: Optional[str]
    impact: str  # high, medium, low
    effort: str  # low, medium, high
    violation_source: Optional[str] = None


class QualitySuggestionGenerator:
    """Generate improvement suggestions from validation results"""

    def __init__(self):
        """Initialize suggestion generator with pattern mappings"""
        # Map violation patterns to suggestions
        # Each pattern has both code and violation text patterns
        self.violation_patterns = {
            # Pydantic v1 legacy patterns
            r"(\.dict\s*\(|\.dict\(\)|pydantic v1 \.dict)": {
                "type": "onex_compliance",
                "priority": 9,
                "title": "Migrate from Pydantic v1 .dict() to .model_dump()",
                "description": "Legacy Pydantic v1 method detected. Use .model_dump() for Pydantic v2 compatibility.",
                "code_example": "# Old:\ndata = model.dict()\n\n# New:\ndata = model.model_dump()",
                "impact": "high",
                "effort": "low",
            },
            r"(\.json\s*\(|\.json\(\)|pydantic v1 \.json)": {
                "type": "onex_compliance",
                "priority": 9,
                "title": "Migrate from Pydantic v1 .json() to .model_dump_json()",
                "description": "Legacy Pydantic v1 method detected. Use .model_dump_json() for Pydantic v2 compatibility.",
                "code_example": "# Old:\njson_str = model.json()\n\n# New:\njson_str = model.model_dump_json()",
                "impact": "high",
                "effort": "low",
            },
            r"(\.copy\s*\(|\.copy\(\)|pydantic v1 \.copy)": {
                "type": "onex_compliance",
                "priority": 9,
                "title": "Migrate from Pydantic v1 .copy() to .model_copy()",
                "description": "Legacy Pydantic v1 method detected. Use .model_copy() for Pydantic v2 compatibility.",
                "code_example": "# Old:\nnew_model = model.copy(update={'field': 'value'})\n\n# New:\nnew_model = model.model_copy(update={'field': 'value'})",
                "impact": "high",
                "effort": "low",
            },
            r"(@validator\s*\(|@validator|validator decorator)": {
                "type": "onex_compliance",
                "priority": 8,
                "title": "Migrate from @validator to @field_validator",
                "description": "Legacy Pydantic v1 decorator. Use @field_validator for Pydantic v2.",
                "code_example": "# Old:\n@validator('field_name')\ndef validate_field(cls, v):\n    return v\n\n# New:\n@field_validator('field_name')\n@classmethod\ndef validate_field(cls, v):\n    return v",
                "impact": "high",
                "effort": "low",
            },
            r"(@root_validator\s*\(|@root_validator|root_validator)": {
                "type": "onex_compliance",
                "priority": 8,
                "title": "Migrate from @root_validator to @model_validator",
                "description": "Legacy Pydantic v1 decorator. Use @model_validator for Pydantic v2.",
                "code_example": "# Old:\n@root_validator\ndef validate_model(cls, values):\n    return values\n\n# New:\n@model_validator(mode='before')\n@classmethod\ndef validate_model(cls, values):\n    return values",
                "impact": "high",
                "effort": "low",
            },
            # Type safety patterns
            r":\s*Any\b": {
                "type": "quality",
                "priority": 10,
                "title": "Remove Any type annotations",
                "description": "Any types are forbidden in ONEX. Use specific types or generics.",
                "code_example": "# Bad:\ndef process(data: Any) -> Any:\n    pass\n\n# Good:\ndef process(data: Dict[str, str]) -> List[str]:\n    pass",
                "impact": "high",
                "effort": "medium",
            },
            # Naming conventions
            r"class\s+[a-z]\w*\([^)]*BaseModel[^)]*\)": {
                "type": "architectural",
                "priority": 7,
                "title": "Use CamelCase for Pydantic models",
                "description": "Pydantic models must follow CamelCase naming with 'Model' prefix.",
                "code_example": "# Bad:\nclass user_config(BaseModel):\n    pass\n\n# Good:\nclass ModelUserConfig(BaseModel):\n    pass",
                "impact": "medium",
                "effort": "low",
            },
            # Dependency injection
            r"\b(Database|Connection|Client)\(\)": {
                "type": "architectural",
                "priority": 8,
                "title": "Use registry injection instead of direct instantiation",
                "description": "Services should be injected via registry, not instantiated directly.",
                "code_example": "# Bad:\ndef __init__(self):\n    self.db = Database()\n\n# Good:\ndef __init__(self, registry: BaseOnexRegistry):\n    self.db = registry.get(DatabaseService)",
                "impact": "high",
                "effort": "medium",
            },
            # Import patterns
            r"from\s+\.\.+\w+\s+import": {
                "type": "quality",
                "priority": 5,
                "title": "Replace multi-level relative imports with absolute imports",
                "description": "Use absolute imports for better clarity and maintainability.",
                "code_example": "# Bad:\nfrom ...utils import helper\n\n# Good:\nfrom omnibase.utils import helper",
                "impact": "medium",
                "effort": "low",
            },
            r"import\s+os": {
                "type": "architectural",
                "priority": 6,
                "title": "Use container for OS operations",
                "description": "Direct OS imports should be avoided. Use injected services.",
                "code_example": "# Bad:\nimport os\npath = os.path.join(...)\n\n# Good:\ndef __init__(self, registry: BaseOnexRegistry):\n    self.path_service = registry.get(PathService)",
                "impact": "medium",
                "effort": "medium",
            },
        }

        # Node type specific requirements
        self.node_type_requirements = {
            "effect": {
                "required_methods": ["execute_effect", "run_effect"],
                "recommended_mixins": [
                    "EventBusMixin",
                    "CachingMixin",
                    "HealthCheckMixin",
                ],
                "base_class": "NodeEffect",
            },
            "compute": {
                "required_methods": ["execute_compute", "run_compute"],
                "recommended_mixins": [],
                "base_class": "NodeCompute",
            },
            "reducer": {
                "required_methods": ["execute_reduction", "run_reduction"],
                "recommended_mixins": ["StateMixin"],
                "base_class": "NodeReducer",
            },
            "orchestrator": {
                "required_methods": ["execute_orchestration", "run_orchestration"],
                "recommended_mixins": ["EventBusMixin", "WorkflowMixin"],
                "base_class": "NodeOrchestrator",
            },
        }

    async def generate_suggestions(
        self, validation_result: Dict[str, Any], code: str, node_type: str
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable improvement suggestions.

        Args:
            validation_result: Validation result from quality service
            code: Source code being analyzed
            node_type: Type of node (effect, compute, reducer, orchestrator)

        Returns:
            List of suggestion dictionaries sorted by priority
        """
        suggestions = []

        # 1. Generate suggestions from violations
        violations = validation_result.get("violations", [])
        for violation in violations:
            suggestion = await self._generate_suggestion_for_violation(
                violation, code, node_type
            )
            if suggestion:
                suggestions.append(suggestion)

        # 2. Generate suggestions from warnings
        warnings = validation_result.get("warnings", [])
        for warning in warnings:
            suggestion = await self._generate_suggestion_for_warning(
                warning, code, node_type
            )
            if suggestion:
                suggestions.append(suggestion)

        # 3. Generate suggestions based on quality score
        quality_score = validation_result.get("quality_score", 0.0)
        if quality_score < 0.8:
            quality_suggestions = await self._suggest_quality_improvements(
                code, node_type, quality_score
            )
            suggestions.extend(quality_suggestions)

        # 4. Generate suggestions based on ONEX compliance score
        onex_score = validation_result.get("onex_compliance_score", 0.0)
        if onex_score < 0.8:
            onex_suggestions = await self._suggest_onex_improvements(
                code, node_type, onex_score
            )
            suggestions.extend(onex_suggestions)

        # 5. Generate node type specific suggestions
        node_suggestions = await self._suggest_node_type_improvements(code, node_type)
        suggestions.extend(node_suggestions)

        # Remove duplicates and sort by priority
        unique_suggestions = self._deduplicate_suggestions(suggestions)
        return sorted(unique_suggestions, key=lambda x: x["priority"], reverse=True)

    async def _generate_suggestion_for_violation(
        self, violation: str, code: str, node_type: str
    ) -> Optional[Dict[str, Any]]:
        """Generate specific suggestion for a violation"""
        # First, try to match violation text directly to be more specific
        for pattern, template in self.violation_patterns.items():
            if re.search(pattern, violation, re.IGNORECASE):
                return {**template, "violation_source": violation}

        # If no violation text match, check code patterns
        for pattern, template in self.violation_patterns.items():
            if re.search(pattern, code):
                return {**template, "violation_source": violation}

        # Generate generic suggestion for unmapped violations
        return {
            "type": "quality",
            "priority": 7,
            "title": "Address validation violation",
            "description": f"Fix: {violation}",
            "code_example": None,
            "impact": "high",
            "effort": "medium",
            "violation_source": violation,
        }

    async def _generate_suggestion_for_warning(
        self, warning: str, code: str, node_type: str
    ) -> Optional[Dict[str, Any]]:
        """Generate suggestion for a warning (lower priority than violations)"""
        # Architectural era warnings
        if "outdated architectural patterns" in warning.lower():
            return {
                "type": "architectural",
                "priority": 6,
                "title": "Modernize architectural patterns",
                "description": warning,
                "code_example": "Consider using modern ONEX patterns: registry injection, contract-driven design, protocol-based interfaces",
                "impact": "medium",
                "effort": "high",
                "violation_source": warning,
            }

        # Generic warning suggestion
        return {
            "type": "quality",
            "priority": 4,
            "title": "Address quality warning",
            "description": warning,
            "code_example": None,
            "impact": "low",
            "effort": "low",
            "violation_source": warning,
        }

    async def _suggest_quality_improvements(
        self, code: str, node_type: str, quality_score: float
    ) -> List[Dict[str, Any]]:
        """Suggest improvements based on code analysis"""
        suggestions = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        # Check for error handling
        has_try_except = any(isinstance(node, ast.Try) for node in ast.walk(tree))
        if not has_try_except:
            suggestions.append(
                {
                    "type": "quality",
                    "priority": 7,
                    "title": "Add error handling",
                    "description": "Functions lack try/except blocks for robust error handling",
                    "code_example": "try:\n    # Your code here\n    result = risky_operation()\nexcept SpecificError as e:\n    logger.error(f'Operation failed: {e}')\n    raise OnexError(CoreErrorCode.OPERATION_FAILED) from e",
                    "impact": "high",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        # Check for type hints
        functions_without_hints = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.returns and node.name not in [
                    "__init__",
                    "__str__",
                    "__repr__",
                ]:
                    functions_without_hints.append(node.name)

        if functions_without_hints:
            suggestions.append(
                {
                    "type": "quality",
                    "priority": 6,
                    "title": "Add type hints to functions",
                    "description": f"Functions missing return type hints: {', '.join(functions_without_hints[:3])}",
                    "code_example": 'def process_data(input: List[str]) -> Dict[str, Any]:\n    """Process input data and return results"""\n    return {\'processed\': input}',
                    "impact": "medium",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        # Check for documentation
        has_docstrings = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if ast.get_docstring(node):
                    has_docstrings = True
                    break

        if not has_docstrings:
            suggestions.append(
                {
                    "type": "quality",
                    "priority": 5,
                    "title": "Add docstrings to classes and functions",
                    "description": "Code lacks proper documentation",
                    "code_example": '"""\\nBrief description.\\n\\nArgs:\\n    param: Description\\n\\nReturns:\\n    Description\\n"""',
                    "impact": "medium",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        # Check for logging
        has_logging = "logger" in code or "log" in code.lower()
        if not has_logging:
            suggestions.append(
                {
                    "type": "quality",
                    "priority": 6,
                    "title": "Add structured logging",
                    "description": "No logging detected. Add structured logging for observability.",
                    "code_example": "logger = logging.getLogger(__name__)\n\nlogger.info('Operation started', extra={'correlation_id': correlation_id})\nlogger.error('Operation failed', exc_info=True)",
                    "impact": "high",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        return suggestions

    async def _suggest_onex_improvements(
        self, code: str, node_type: str, onex_score: float
    ) -> List[Dict[str, Any]]:
        """Suggest ONEX compliance improvements"""
        suggestions = []

        # Check for registry injection
        has_registry = "registry:" in code or "BaseOnexRegistry" in code
        if not has_registry:
            suggestions.append(
                {
                    "type": "onex_compliance",
                    "priority": 8,
                    "title": "Implement registry injection",
                    "description": "Use registry pattern for dependency injection",
                    "code_example": "def __init__(self, registry: BaseOnexRegistry):\n    super().__init__(registry)\n    self.service = registry.get(YourService)",
                    "impact": "high",
                    "effort": "medium",
                    "violation_source": None,
                }
            )

        # Check for proper ONEX error handling
        has_onex_error = "OnexError" in code or "CoreErrorCode" in code
        if not has_onex_error:
            suggestions.append(
                {
                    "type": "onex_compliance",
                    "priority": 7,
                    "title": "Use OnexError for exceptions",
                    "description": "Replace generic exceptions with OnexError",
                    "code_example": "from omnibase.errors import OnexError\nfrom omnibase.errors.error_codes import CoreErrorCode\n\nraise OnexError(\n    code=CoreErrorCode.VALIDATION_FAILED,\n    message='Validation failed',\n    context={'field': 'value'}\n)",
                    "impact": "high",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        # Check for contract patterns
        has_contract = "contract" in code.lower() or "ModelContract" in code
        if not has_contract and node_type != "orchestrator":
            suggestions.append(
                {
                    "type": "onex_compliance",
                    "priority": 6,
                    "title": "Add contract definitions",
                    "description": "Use contract-driven patterns for better type safety",
                    "code_example": "from omnibase.models import ModelContractBase\n\nclass YourContract(ModelContractBase):\n    input_schema: Dict[str, Any]\n    output_schema: Dict[str, Any]",
                    "impact": "medium",
                    "effort": "medium",
                    "violation_source": None,
                }
            )

        # Check for structured logging
        has_emit_log = "emit_log_event" in code
        if not has_emit_log:
            suggestions.append(
                {
                    "type": "onex_compliance",
                    "priority": 5,
                    "title": "Use structured logging with emit_log_event",
                    "description": "Implement ONEX structured logging pattern",
                    "code_example": "self.emit_log_event(\n    level='info',\n    message='Operation completed',\n    context={'duration_ms': elapsed}\n)",
                    "impact": "medium",
                    "effort": "low",
                    "violation_source": None,
                }
            )

        return suggestions

    async def _suggest_node_type_improvements(
        self, code: str, node_type: str
    ) -> List[Dict[str, Any]]:
        """Suggest node type specific improvements"""
        suggestions = []

        requirements = self.node_type_requirements.get(node_type)
        if not requirements:
            return suggestions

        # Check for required methods
        for method in requirements["required_methods"]:
            if method not in code:
                suggestions.append(
                    {
                        "type": "architectural",
                        "priority": 9,
                        "title": f"Implement required method: {method}",
                        "description": f"{node_type.upper()} nodes must implement {method} method",
                        "code_example": f'async def {method}(self, input_data: Any) -> Any:\n    """Implement {node_type} logic here"""\n    # Your implementation\n    return result',
                        "impact": "high",
                        "effort": "high",
                        "violation_source": None,
                    }
                )

        # Check for base class
        base_class = requirements["base_class"]
        if base_class not in code:
            suggestions.append(
                {
                    "type": "architectural",
                    "priority": 8,
                    "title": f"Inherit from {base_class}",
                    "description": f"{node_type.upper()} nodes should inherit from {base_class}",
                    "code_example": f"class YourNode{node_type.capitalize()}({base_class}):\n    def __init__(self, registry: BaseOnexRegistry):\n        super().__init__(registry)",
                    "impact": "high",
                    "effort": "medium",
                    "violation_source": None,
                }
            )

        # Check for recommended mixins
        for mixin in requirements["recommended_mixins"]:
            if mixin not in code:
                suggestions.append(
                    {
                        "type": "architectural",
                        "priority": 4,
                        "title": f"Consider adding {mixin}",
                        "description": f"Recommended for {node_type.upper()} nodes to enhance functionality",
                        "code_example": f"class YourNode({base_class}, {mixin}):\n    pass",
                        "impact": "low",
                        "effort": "low",
                        "violation_source": None,
                    }
                )

        return suggestions

    def _deduplicate_suggestions(
        self, suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate suggestions based on title"""
        seen_titles = set()
        unique = []

        for suggestion in suggestions:
            title = suggestion["title"]
            if title not in seen_titles:
                seen_titles.add(title)
                unique.append(suggestion)

        return unique
