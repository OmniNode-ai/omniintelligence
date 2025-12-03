"""
Quality Scoring Compute Node

Assesses code quality across 6 dimensions with real analysis.
"""

import ast
import re
from typing import Any

from omnibase_core.nodes import NodeCompute
from pydantic import BaseModel, Field


class ModelQualityScoringInput(BaseModel):
    """Input model for quality scoring."""
    file_path: str
    content: str
    language: str
    project_name: str
    assessment_type: str = "full"


class ModelQualityScoringOutput(BaseModel):
    """Output model for quality scoring."""
    success: bool
    overall_score: float
    dimensions: dict[str, float]
    onex_compliant: bool
    compliance_issues: list[str] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class ModelQualityScoringConfig(BaseModel):
    """Configuration for quality scoring."""
    quality_thresholds: dict[str, float] = Field(default_factory=lambda: {
        "maintainability": 0.7,
        "readability": 0.7,
        "complexity": 0.6,
        "documentation": 0.6,
        "testing": 0.7,
        "security": 0.8,
    })
    onex_validation_enabled: bool = True
    generate_recommendations: bool = True
    dimension_weights: dict[str, float] = Field(default_factory=lambda: {
        "maintainability": 0.20,
        "readability": 0.15,
        "complexity": 0.20,
        "documentation": 0.15,
        "testing": 0.15,
        "security": 0.15,
    })


class PythonCodeAnalyzer:
    """Analyzes Python code for quality metrics."""

    def __init__(self, content: str, file_path: str):
        """Initialize analyzer with code content."""
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')
        self.tree = None
        self.parse_error = None

        try:
            self.tree = ast.parse(content)
        except SyntaxError as e:
            self.parse_error = str(e)

    def analyze_complexity(self) -> tuple[float, list[str]]:
        """
        Analyze code complexity using cyclomatic complexity approximation.

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.0, [f"Syntax error prevents complexity analysis: {self.parse_error}"]

        issues = []
        complexity_counts = []

        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.function_complexities = {}

            def visit_FunctionDef(self, node):
                # Calculate complexity for this function
                complexity = 1  # Base complexity
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1

                self.function_complexities[node.name] = complexity
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

        visitor = ComplexityVisitor()
        visitor.visit(self.tree)

        for func_name, complexity in visitor.function_complexities.items():
            complexity_counts.append(complexity)
            if complexity > 15:
                issues.append(f"Function '{func_name}' has high complexity ({complexity})")
            elif complexity > 10:
                issues.append(f"Function '{func_name}' has moderate complexity ({complexity})")

        if not complexity_counts:
            return 1.0, []

        # Score based on average complexity (lower is better)
        avg_complexity = sum(complexity_counts) / len(complexity_counts)
        max_complexity = max(complexity_counts)

        # Score formula: penalize both average and max complexity
        score = max(0.0, 1.0 - (avg_complexity / 20.0) - (max_complexity / 40.0))
        return min(1.0, max(0.0, score)), issues

    def analyze_documentation(self) -> tuple[float, list[str]]:
        """
        Analyze documentation coverage (docstrings and comments).

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.0, [f"Syntax error prevents documentation analysis: {self.parse_error}"]

        issues = []

        # Count functions/classes and their docstrings
        class DocVisitor(ast.NodeVisitor):
            def __init__(self):
                self.functions = []
                self.classes = []

            def visit_FunctionDef(self, node):
                docstring = ast.get_docstring(node)
                self.functions.append({
                    'name': node.name,
                    'has_docstring': docstring is not None,
                    'is_private': node.name.startswith('_') and not node.name.startswith('__'),
                })
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                docstring = ast.get_docstring(node)
                self.classes.append({
                    'name': node.name,
                    'has_docstring': docstring is not None,
                })
                self.generic_visit(node)

        visitor = DocVisitor()
        visitor.visit(self.tree)

        # Calculate comment ratio
        code_lines = [line for line in self.lines if line.strip() and not line.strip().startswith('#')]
        comment_lines = [line for line in self.lines if line.strip().startswith('#')]
        comment_ratio = len(comment_lines) / max(1, len(code_lines))

        # Calculate docstring coverage
        public_functions = [f for f in visitor.functions if not f['is_private']]
        documented_functions = [f for f in public_functions if f['has_docstring']]
        documented_classes = [c for c in visitor.classes if c['has_docstring']]

        function_coverage = len(documented_functions) / max(1, len(public_functions)) if public_functions else 1.0
        class_coverage = len(documented_classes) / max(1, len(visitor.classes)) if visitor.classes else 1.0

        # Generate issues
        for func in public_functions:
            if not func['has_docstring']:
                issues.append(f"Public function '{func['name']}' missing docstring")

        for cls in visitor.classes:
            if not cls['has_docstring']:
                issues.append(f"Class '{cls['name']}' missing docstring")

        if comment_ratio < 0.05:
            issues.append(f"Low comment ratio ({comment_ratio:.1%})")

        # Combined score
        score = (function_coverage * 0.4 + class_coverage * 0.4 + min(1.0, comment_ratio * 10) * 0.2)
        return score, issues

    def analyze_maintainability(self) -> tuple[float, list[str]]:
        """
        Analyze maintainability (function length, nesting depth).

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.0, [f"Syntax error prevents maintainability analysis: {self.parse_error}"]

        issues = []

        class MaintainabilityVisitor(ast.NodeVisitor):
            def __init__(self, lines):
                self.lines = lines
                self.function_lengths = {}
                self.max_nesting_depths = {}

            def visit_FunctionDef(self, node):
                # Calculate function length
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    length = node.end_lineno - node.lineno
                    self.function_lengths[node.name] = length

                # Calculate max nesting depth
                max_depth = self._get_max_depth(node, 0)
                self.max_nesting_depths[node.name] = max_depth

                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

            def _get_max_depth(self, node, current_depth):
                max_depth = current_depth
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                        child_depth = self._get_max_depth(child, current_depth + 1)
                        max_depth = max(max_depth, child_depth)
                return max_depth

        visitor = MaintainabilityVisitor(self.lines)
        visitor.visit(self.tree)

        # Analyze function lengths
        length_penalties = []
        for func_name, length in visitor.function_lengths.items():
            if length > 100:
                issues.append(f"Function '{func_name}' is very long ({length} lines)")
                length_penalties.append(1.0)
            elif length > 50:
                issues.append(f"Function '{func_name}' is long ({length} lines)")
                length_penalties.append(0.5)
            else:
                length_penalties.append(0.0)

        # Analyze nesting depths
        depth_penalties = []
        for func_name, depth in visitor.max_nesting_depths.items():
            if depth > 5:
                issues.append(f"Function '{func_name}' has deep nesting (depth {depth})")
                depth_penalties.append(1.0)
            elif depth > 3:
                issues.append(f"Function '{func_name}' has moderate nesting (depth {depth})")
                depth_penalties.append(0.5)
            else:
                depth_penalties.append(0.0)

        # Calculate score
        if not length_penalties and not depth_penalties:
            return 1.0, []

        avg_length_penalty = sum(length_penalties) / max(1, len(length_penalties)) if length_penalties else 0.0
        avg_depth_penalty = sum(depth_penalties) / max(1, len(depth_penalties)) if depth_penalties else 0.0

        score = 1.0 - (avg_length_penalty * 0.5 + avg_depth_penalty * 0.5)
        return max(0.0, score), issues

    def analyze_naming(self) -> tuple[float, list[str]]:
        """
        Analyze naming conventions (snake_case, descriptive names).

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.0, [f"Syntax error prevents naming analysis: {self.parse_error}"]

        issues = []

        class NamingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.function_names = []
                self.class_names = []
                self.variable_names = []

            def visit_FunctionDef(self, node):
                self.function_names.append(node.name)
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                self.class_names.append(node.name)
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    self.variable_names.append(node.id)
                self.generic_visit(node)

        visitor = NamingVisitor()
        visitor.visit(self.tree)

        # Check function naming (should be snake_case)
        function_violations = 0
        for name in visitor.function_names:
            if name.startswith('_'):
                continue
            if not re.match(r'^[a-z_][a-z0-9_]*$', name):
                issues.append(f"Function '{name}' doesn't follow snake_case convention")
                function_violations += 1
            elif len(name) < 3 and name not in ['id', 'ok', 'db', 'ui', 'ai', 'io']:
                issues.append(f"Function '{name}' has non-descriptive name")
                function_violations += 1

        # Check class naming (should be PascalCase)
        class_violations = 0
        for name in visitor.class_names:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
                issues.append(f"Class '{name}' doesn't follow PascalCase convention")
                class_violations += 1

        # Calculate score
        total_items = len(visitor.function_names) + len(visitor.class_names)
        total_violations = function_violations + class_violations

        if total_items == 0:
            return 1.0, []

        score = 1.0 - (total_violations / total_items)
        return max(0.0, score), issues

    def analyze_testing(self) -> tuple[float, list[str]]:
        """
        Analyze testing presence and quality indicators.

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.5, ["Unable to fully analyze testing due to syntax error"]

        issues = []
        is_test_file = 'test_' in self.file_path or '_test.py' in self.file_path

        if is_test_file:
            # Analyze test structure
            class TestVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.test_functions = []
                    self.assertions = 0
                    self.has_fixtures = False

                def visit_FunctionDef(self, node):
                    if node.name.startswith('test_'):
                        self.test_functions.append(node.name)
                    if any(decorator.id == 'fixture' if isinstance(decorator, ast.Name) else False
                           for decorator in node.decorator_list):
                        self.has_fixtures = True
                    self.generic_visit(node)

                visit_AsyncFunctionDef = visit_FunctionDef

                def visit_Assert(self, node):
                    self.assertions += 1
                    self.generic_visit(node)

                def visit_Call(self, node):
                    # Count assert_ method calls
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr.startswith('assert'):
                            self.assertions += 1
                    self.generic_visit(node)

            visitor = TestVisitor()
            visitor.visit(self.tree)

            if not visitor.test_functions:
                issues.append("No test functions found in test file")
                return 0.3, issues

            avg_assertions = visitor.assertions / len(visitor.test_functions)
            if avg_assertions < 1:
                issues.append("Test functions have few assertions")

            score = min(1.0, 0.5 + (avg_assertions / 5.0) * 0.3 + (0.2 if visitor.has_fixtures else 0.0))
            return score, issues
        else:
            # Check for testable structure
            class CodeVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.public_functions = 0
                    self.functions_with_types = 0

                def visit_FunctionDef(self, node):
                    if not node.name.startswith('_'):
                        self.public_functions += 1
                        if node.returns or any(arg.annotation for arg in node.args.args):
                            self.functions_with_types += 1
                    self.generic_visit(node)

                visit_AsyncFunctionDef = visit_FunctionDef

            visitor = CodeVisitor()
            visitor.visit(self.tree)

            if visitor.public_functions == 0:
                return 0.8, []  # No functions to test

            type_coverage = visitor.functions_with_types / visitor.public_functions
            issues.append("No tests detected (score based on code testability)")

            if type_coverage < 0.5:
                issues.append("Low type hint coverage reduces testability")

            score = 0.4 + (type_coverage * 0.3)
            return score, issues

    def analyze_security(self) -> tuple[float, list[str]]:
        """
        Analyze basic security indicators.

        Returns:
            Tuple of (score, issues) where score is 0.0-1.0
        """
        if self.parse_error:
            return 0.5, ["Unable to fully analyze security due to syntax error"]

        issues = []
        security_score = 1.0

        # Check for dangerous patterns
        dangerous_patterns = {
            r'\beval\s*\(': "Use of eval() is dangerous",
            r'\bexec\s*\(': "Use of exec() is dangerous",
            r'\b__import__\s*\(': "Dynamic imports can be dangerous",
            r'shell\s*=\s*True': "shell=True in subprocess is dangerous",
            r'pickle\.loads': "pickle.loads on untrusted data is dangerous",
        }

        for pattern, message in dangerous_patterns.items():
            if re.search(pattern, self.content):
                issues.append(message)
                security_score -= 0.15

        # Check for hardcoded secrets patterns
        secret_patterns = {
            r'password\s*=\s*["\'][^"\']+["\']': "Possible hardcoded password",
            r'api[_-]?key\s*=\s*["\'][^"\']+["\']': "Possible hardcoded API key",
            r'secret\s*=\s*["\'][^"\']+["\']': "Possible hardcoded secret",
        }

        for pattern, message in secret_patterns.items():
            matches = re.finditer(pattern, self.content, re.IGNORECASE)
            for match in matches:
                if 'os.environ' not in match.group() and 'getenv' not in match.group():
                    issues.append(message)
                    security_score -= 0.1

        # Check for SQL injection patterns
        if re.search(r'execute\s*\([^)]*%s[^)]*\)', self.content):
            issues.append("Possible SQL injection vulnerability (use parameterized queries)")
            security_score -= 0.2

        return max(0.0, security_score), issues


class QualityScoringCompute(NodeCompute):
    """Compute node for quality assessment with real analysis."""

    def __init__(
        self,
        container: Any | None = None,
        config: ModelQualityScoringConfig | None = None,
    ) -> None:
        """Initialize the quality scoring compute node.

        Args:
            container: Optional ONEX container for dependency injection (not used in standalone mode)
            config: Optional configuration for the node
        """
        # Only initialize base class with proper container (has compute_cache_config)
        # In standalone/test mode, container is None, so we skip super().__init__
        if container is not None and hasattr(container, "compute_cache_config"):
            super().__init__(container)

        self.config = config or ModelQualityScoringConfig()

    async def process(self, input_data: ModelQualityScoringInput) -> ModelQualityScoringOutput:
        """
        Assess code quality across 6 dimensions.

        Args:
            input_data: Input containing code content and metadata

        Returns:
            Quality assessment with scores and recommendations
        """
        # Only analyze Python code for now
        if input_data.language.lower() not in ['python', 'py']:
            return ModelQualityScoringOutput(
                success=False,
                overall_score=0.0,
                dimensions={
                    "maintainability": 0.0,
                    "readability": 0.0,
                    "complexity": 0.0,
                    "documentation": 0.0,
                    "testing": 0.0,
                    "security": 0.0,
                },
                onex_compliant=False,
                compliance_issues=["Only Python code analysis is currently supported"],
                recommendations=[],
            )

        # Handle empty content
        if not input_data.content.strip():
            return ModelQualityScoringOutput(
                success=False,
                overall_score=0.0,
                dimensions={
                    "maintainability": 0.0,
                    "readability": 0.0,
                    "complexity": 0.0,
                    "documentation": 0.0,
                    "testing": 0.0,
                    "security": 0.0,
                },
                onex_compliant=False,
                compliance_issues=["Empty file content"],
                recommendations=[{"type": "general", "message": "Add code to the file"}],
            )

        # Create analyzer
        analyzer = PythonCodeAnalyzer(input_data.content, input_data.file_path)

        # Run all analyses
        complexity_score, complexity_issues = analyzer.analyze_complexity()
        documentation_score, documentation_issues = analyzer.analyze_documentation()
        maintainability_score, maintainability_issues = analyzer.analyze_maintainability()
        naming_score, naming_issues = analyzer.analyze_naming()
        testing_score, testing_issues = analyzer.analyze_testing()
        security_score, security_issues = analyzer.analyze_security()

        # Combine naming into readability
        readability_score = (naming_score * 0.6 + documentation_score * 0.4)

        # Collect dimensions
        dimensions = {
            "maintainability": round(maintainability_score, 2),
            "readability": round(readability_score, 2),
            "complexity": round(complexity_score, 2),
            "documentation": round(documentation_score, 2),
            "testing": round(testing_score, 2),
            "security": round(security_score, 2),
        }

        # Get config (default if not available)
        config = ModelQualityScoringConfig()

        # Calculate weighted overall score
        overall_score = sum(
            dimensions[dim] * config.dimension_weights[dim]
            for dim in dimensions
        )
        overall_score = round(overall_score, 2)

        # Check ONEX compliance and collect issues
        compliance_issues = []
        all_issues = (
            complexity_issues + documentation_issues + maintainability_issues +
            naming_issues + testing_issues + security_issues
        )

        # ONEX compliance checks
        onex_compliant = True
        for dim, score in dimensions.items():
            threshold = config.quality_thresholds[dim]
            if score < threshold:
                onex_compliant = False
                compliance_issues.append(
                    f"{dim.title()} score ({score:.2f}) below threshold ({threshold:.2f})"
                )

        # Generate recommendations
        recommendations = []

        if complexity_score < 0.7:
            recommendations.append({
                "type": "complexity",
                "priority": "high" if complexity_score < 0.5 else "medium",
                "message": "Refactor complex functions using extraction and simplification",
                "details": complexity_issues[:3],
            })

        if documentation_score < 0.7:
            recommendations.append({
                "type": "documentation",
                "priority": "high" if documentation_score < 0.5 else "medium",
                "message": "Add docstrings to public functions and classes",
                "details": documentation_issues[:3],
            })

        if maintainability_score < 0.7:
            recommendations.append({
                "type": "maintainability",
                "priority": "high" if maintainability_score < 0.5 else "medium",
                "message": "Reduce function length and nesting depth",
                "details": maintainability_issues[:3],
            })

        if readability_score < 0.7:
            recommendations.append({
                "type": "readability",
                "priority": "medium",
                "message": "Improve naming conventions and code clarity",
                "details": naming_issues[:3],
            })

        if testing_score < 0.7:
            recommendations.append({
                "type": "testing",
                "priority": "high",
                "message": "Add comprehensive unit tests with assertions",
                "details": testing_issues[:2],
            })

        if security_score < 0.8:
            recommendations.append({
                "type": "security",
                "priority": "critical" if security_score < 0.6 else "high",
                "message": "Address security vulnerabilities immediately",
                "details": security_issues,
            })

        return ModelQualityScoringOutput(
            success=True,
            overall_score=overall_score,
            dimensions=dimensions,
            onex_compliant=onex_compliant,
            compliance_issues=compliance_issues,
            recommendations=recommendations,
        )
