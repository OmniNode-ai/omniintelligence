"""
Quality Scorer for Archon Intelligence Service

Advanced quality assessment for extracted entities and code patterns.
Combines multiple scoring algorithms for comprehensive quality evaluation.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from models.entity_models import EntityType, KnowledgeEntity, PatternMatch, QualityScore

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    Multi-dimensional quality scorer for code entities and patterns.

    Evaluates code quality across multiple dimensions including:
    - Complexity (cyclomatic, cognitive)
    - Maintainability (readability, structure)
    - Documentation coverage and quality
    - Temporal relevance and freshness
    - Pattern compliance and best practices
    """

    def __init__(self):
        """Initialize quality scorer with scoring weights and thresholds"""

        # Scoring weights for different quality dimensions
        self.quality_weights = {
            "complexity": 0.20,
            "maintainability": 0.20,
            "documentation": 0.15,
            "temporal_relevance": 0.15,
            "pattern_compliance": 0.15,
            "architectural_compliance": 0.15,
        }

        # Complexity thresholds
        self.complexity_thresholds = {
            "cyclomatic_low": 5,
            "cyclomatic_medium": 10,
            "cyclomatic_high": 15,
            "cognitive_low": 7,
            "cognitive_medium": 15,
            "cognitive_high": 25,
            "max_lines_function": 50,
            "max_lines_class": 300,
        }

        # Architectural era definitions (based on omnibase_3 ONEX patterns)
        self.architectural_eras = {
            "pre_archon": {
                "score_modifier": -0.2,
                "patterns": [
                    r"from\s+\*\s+import",
                    r"class.*\(object\):",
                    r"print\s*\(",
                    r"except\s*:",
                ],
            },
            "early_archon": {
                "score_modifier": -0.1,
                "patterns": [
                    r"def\s+main\(\):",
                    r"if\s+__name__\s*==\s*['\"]__main__['\"]:",
                    r"ConfigParser",
                ],
            },
            "modern_archon": {
                "score_modifier": 0.0,
                "patterns": [
                    r"from\s+typing\s+import",
                    r"@dataclass",
                    r"async\s+def",
                    r"FastAPI",
                ],
            },
            "advanced_archon": {
                "score_modifier": 0.1,
                "patterns": [
                    r"@inject",
                    r"Protocol",
                    r"from\s+omnibase\.core",
                    r"ModelOnex",
                ],
            },
        }

        # ONEX Architectural compliance patterns (adapted for Archon)
        self.architectural_patterns = {
            "critical_failures": [
                (
                    r"Any\s*[,\)\]]|from\s+typing\s+import.*Any",
                    "any_type_usage",
                    "Uses Any type - defeats type safety",
                ),
                (
                    r"from\s+.*\s+import\s+\*",
                    "wildcard_import",
                    "Wildcard imports break explicit dependencies",
                ),
                (
                    r"[A-Z][a-z]+\(\)",
                    "direct_instantiation",
                    "Direct class instantiation - should use injection",
                ),
            ],
            "moderate_issues": [
                (
                    r"def\s+[a-z]+[A-Z]",
                    "camelcase_function",
                    "Functions should use snake_case",
                ),
                (
                    r"import\s+os\b(?!.*path)",
                    "direct_os_import",
                    "Direct OS imports - use abstractions",
                ),
                (
                    r"global\s+\w+",
                    "global_variable",
                    "Global variables break encapsulation",
                ),
            ],
            "modern_patterns": [
                (
                    r"@inject|@Inject",
                    "dependency_injection",
                    "Uses dependency injection",
                ),
                (r":\s*Protocol", "protocol_usage", "Uses protocols for interfaces"),
                (
                    r"raise\s+\w+Error\(",
                    "proper_exceptions",
                    "Raises specific exceptions",
                ),
            ],
        }

        # Pattern definitions for quality assessment
        self.quality_patterns = {
            "good_patterns": [
                (r"def\s+\w+\(.*?\)\s*->\s*\w+:", "type_annotations", 0.8),
                (r"class\s+\w+\(.*Protocol.*\):", "protocol_interface", 0.9),
                (r'""".*?"""', "docstring_present", 0.7),
                (r"@\w+\.setter", "property_setter", 0.6),
                (r"with\s+\w+.*?:", "context_manager", 0.8),
                (r"async\s+def", "async_function", 0.7),
            ],
            "code_smells": [
                (r"def\s+\w+\([^)]{50,}\):", "long_parameter_list", -0.6),
                (r"elif.*?elif.*?elif", "deep_conditional", -0.5),
                (r"for.*?for.*?for.*?for", "nested_loops", -0.7),
                (r"global\s+\w+", "global_variable", -0.8),
                (r"exec\(", "exec_usage", -0.9),
                (r"eval\(", "eval_usage", -0.9),
                (r"import\s+\*", "wildcard_import", -0.4),
            ],
            "security_patterns": [
                (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded_password", -1.0),
                (r"api_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded_api_key", -1.0),
                (r"sql\s*=.*?\+.*?", "sql_concatenation", -0.8),
                (r"pickle\.load", "pickle_usage", -0.6),
                (r"subprocess\.(call|run|Popen)", "subprocess_usage", -0.4),
            ],
        }

    def score_entity(self, entity: KnowledgeEntity, content: str = "") -> QualityScore:
        """
        Generate comprehensive quality score for an entity.

        Args:
            entity: Entity to score
            content: Source code content for analysis

        Returns:
            QualityScore with detailed breakdown
        """
        try:
            scores = {}
            reasoning_parts = []

            # Calculate complexity score
            complexity_score, complexity_reason = self._calculate_complexity_score(
                entity, content
            )
            scores["complexity"] = complexity_score
            reasoning_parts.append(f"Complexity: {complexity_reason}")

            # Calculate maintainability score
            maintainability_score, maint_reason = self._calculate_maintainability_score(
                entity, content
            )
            scores["maintainability"] = maintainability_score
            reasoning_parts.append(f"Maintainability: {maint_reason}")

            # Calculate documentation score
            doc_score, doc_reason = self._calculate_documentation_score(entity, content)
            scores["documentation"] = doc_score
            reasoning_parts.append(f"Documentation: {doc_reason}")

            # Calculate temporal relevance
            temporal_score, temporal_reason = self._calculate_temporal_relevance(entity)
            scores["temporal_relevance"] = temporal_score
            reasoning_parts.append(f"Temporal: {temporal_reason}")

            # Calculate pattern compliance
            pattern_score, pattern_reason = self._calculate_pattern_compliance(
                entity, content
            )
            scores["pattern_compliance"] = pattern_score
            reasoning_parts.append(f"Patterns: {pattern_reason}")

            # Calculate architectural compliance (ONEX-inspired)
            arch_score, arch_reason = self._calculate_architectural_compliance(
                entity, content
            )
            scores["architectural_compliance"] = arch_score
            reasoning_parts.append(f"Architecture: {arch_reason}")

            # Calculate weighted overall score
            overall_score = sum(
                scores[dimension] * self.quality_weights[dimension]
                for dimension in scores
            )

            return QualityScore(
                overall_score=max(0.0, min(1.0, overall_score)),  # Clamp to [0, 1]
                temporal_relevance=temporal_score,
                complexity_score=complexity_score,
                maintainability_score=maintainability_score,
                documentation_score=doc_score,
                factors=scores,
                reasoning="; ".join(reasoning_parts),
            )

        except Exception as e:
            logger.error(f"Quality scoring failed for entity {entity.entity_id}: {e}")
            return QualityScore(
                overall_score=0.5,  # Neutral score on error
                temporal_relevance=0.5,
                reasoning=f"Scoring error: {str(e)}",
            )

    def detect_patterns(
        self, content: str, entity: KnowledgeEntity
    ) -> List[PatternMatch]:
        """
        Detect quality patterns, anti-patterns, and code smells.

        Args:
            content: Source code to analyze
            entity: Entity context for pattern detection

        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []

        try:
            # Check for good patterns
            for pattern_regex, pattern_name, confidence in self.quality_patterns[
                "good_patterns"
            ]:
                matches = re.finditer(pattern_regex, content, re.DOTALL | re.MULTILINE)
                for match in matches:
                    patterns.append(
                        PatternMatch(
                            pattern_name=pattern_name,
                            pattern_type="good_practice",
                            confidence=confidence,
                            description=f"Good practice: {pattern_name.replace('_', ' ')}",
                            location={"line": content[: match.start()].count("\n") + 1},
                            severity="info",
                            recommendation="Continue using this pattern",
                        )
                    )

            # Check for code smells
            for pattern_regex, pattern_name, penalty in self.quality_patterns[
                "code_smells"
            ]:
                matches = re.finditer(pattern_regex, content, re.DOTALL | re.MULTILINE)
                for match in matches:
                    patterns.append(
                        PatternMatch(
                            pattern_name=pattern_name,
                            pattern_type="code_smell",
                            confidence=abs(penalty),
                            description=f"Code smell: {pattern_name.replace('_', ' ')}",
                            location={"line": content[: match.start()].count("\n") + 1},
                            severity="warning",
                            recommendation=self._get_smell_recommendation(pattern_name),
                        )
                    )

            # Check for security patterns
            for pattern_regex, pattern_name, penalty in self.quality_patterns[
                "security_patterns"
            ]:
                matches = re.finditer(pattern_regex, content, re.DOTALL | re.MULTILINE)
                for match in matches:
                    patterns.append(
                        PatternMatch(
                            pattern_name=pattern_name,
                            pattern_type="security_issue",
                            confidence=abs(penalty),
                            description=f"Security concern: {pattern_name.replace('_', ' ')}",
                            location={"line": content[: match.start()].count("\n") + 1},
                            severity="error" if abs(penalty) > 0.8 else "warning",
                            recommendation=self._get_security_recommendation(
                                pattern_name
                            ),
                        )
                    )

            # Entity-specific pattern detection
            if entity.entity_type == EntityType.FUNCTION:
                patterns.extend(self._detect_function_patterns(content, entity))
            elif entity.entity_type == EntityType.CLASS:
                patterns.extend(self._detect_class_patterns(content, entity))

            return patterns

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            return []

    def _calculate_complexity_score(
        self, entity: KnowledgeEntity, content: str
    ) -> Tuple[float, str]:
        """Calculate complexity-based quality score"""
        try:
            if entity.entity_type in [EntityType.FUNCTION, EntityType.METHOD]:
                # Cyclomatic complexity for functions
                cyclomatic = self._calculate_cyclomatic_complexity(content)
                cognitive = self._calculate_cognitive_complexity(content)

                # Score based on complexity thresholds
                if cyclomatic <= self.complexity_thresholds["cyclomatic_low"]:
                    complexity_score = 0.9
                    reason = f"Low cyclomatic complexity ({cyclomatic})"
                elif cyclomatic <= self.complexity_thresholds["cyclomatic_medium"]:
                    complexity_score = 0.7
                    reason = f"Moderate cyclomatic complexity ({cyclomatic})"
                elif cyclomatic <= self.complexity_thresholds["cyclomatic_high"]:
                    complexity_score = 0.4
                    reason = f"High cyclomatic complexity ({cyclomatic})"
                else:
                    complexity_score = 0.2
                    reason = f"Very high cyclomatic complexity ({cyclomatic})"

                # Adjust for cognitive complexity
                if cognitive > self.complexity_thresholds["cognitive_high"]:
                    complexity_score *= 0.7
                    reason += f", high cognitive complexity ({cognitive})"

                return complexity_score, reason

            elif entity.entity_type == EntityType.CLASS:
                # Class complexity based on methods and size
                lines = len(content.split("\n"))
                methods = len(re.findall(r"def\s+\w+", content))

                if lines <= 50 and methods <= 5:
                    return 0.9, f"Simple class ({lines} lines, {methods} methods)"
                elif lines <= 150 and methods <= 15:
                    return (
                        0.7,
                        f"Moderate class complexity ({lines} lines, {methods} methods)",
                    )
                else:
                    return 0.4, f"Complex class ({lines} lines, {methods} methods)"

            else:
                # Default complexity assessment
                lines = len(content.split("\n")) if content else 0
                if lines <= 20:
                    return 0.8, f"Simple entity ({lines} lines)"
                elif lines <= 100:
                    return 0.6, f"Moderate entity ({lines} lines)"
                else:
                    return 0.4, f"Large entity ({lines} lines)"

        except Exception as e:
            return 0.5, f"Complexity calculation error: {str(e)}"

    def _calculate_maintainability_score(
        self, entity: KnowledgeEntity, content: str
    ) -> Tuple[float, str]:
        """Calculate maintainability score based on code structure"""
        try:
            score_factors = []

            if content:
                # Check for meaningful naming
                if re.search(r"[a-z_][a-z0-9_]+", entity.name, re.I):
                    score_factors.append(("naming", 0.8))
                else:
                    score_factors.append(("naming", 0.4))

                # Check for proper indentation and structure
                lines = content.split("\n")
                inconsistent_indent = sum(
                    1
                    for line in lines
                    if line.strip() and not line.startswith((" " * 4, "\t"))
                )
                if inconsistent_indent < len(lines) * 0.1:
                    score_factors.append(("formatting", 0.8))
                else:
                    score_factors.append(("formatting", 0.5))

                # Check for reasonable line length
                long_lines = sum(1 for line in lines if len(line) > 100)
                if long_lines < len(lines) * 0.2:
                    score_factors.append(("line_length", 0.7))
                else:
                    score_factors.append(("line_length", 0.4))

            else:
                # Fallback scoring
                score_factors = [("naming", 0.6), ("structure", 0.5)]

            # Calculate weighted average
            avg_score = sum(score for _, score in score_factors) / len(score_factors)

            reason_parts = [f"{factor}={score:.1f}" for factor, score in score_factors]
            reason = f"Maintainability factors: {', '.join(reason_parts)}"

            return avg_score, reason

        except Exception as e:
            return 0.5, f"Maintainability calculation error: {str(e)}"

    def _calculate_documentation_score(
        self, entity: KnowledgeEntity, content: str
    ) -> Tuple[float, str]:
        """Calculate documentation quality score"""
        try:
            if not content:
                return 0.3, "No content available for documentation analysis"

            # Check for docstrings
            has_docstring = bool(re.search(r'""".*?"""', content, re.DOTALL))

            # Check for type annotations
            has_type_hints = bool(re.search(r"->\s*\w+", content))

            # Check for inline comments
            comment_lines = len(re.findall(r"^\s*#[^!]", content, re.MULTILINE))
            code_lines = len(
                [
                    line
                    for line in content.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            )
            comment_ratio = comment_lines / max(code_lines, 1)

            # Score calculation
            doc_score = 0.0
            reasons = []

            if has_docstring:
                doc_score += 0.5
                reasons.append("has docstring")
            else:
                reasons.append("missing docstring")

            if has_type_hints:
                doc_score += 0.3
                reasons.append("has type hints")
            else:
                reasons.append("no type hints")

            if comment_ratio > 0.1:
                doc_score += 0.2
                reasons.append(f"good comments ({comment_ratio:.1%})")
            elif comment_ratio > 0.05:
                doc_score += 0.1
                reasons.append(f"some comments ({comment_ratio:.1%})")
            else:
                reasons.append("few comments")

            return min(doc_score, 1.0), f"Documentation: {', '.join(reasons)}"

        except Exception as e:
            return 0.5, f"Documentation scoring error: {str(e)}"

    def _calculate_temporal_relevance(
        self, entity: KnowledgeEntity
    ) -> Tuple[float, str]:
        """Calculate temporal relevance with ONEX-inspired exponential decay"""
        try:
            # Enhanced temporal relevance with git integration potential
            created_at = entity.metadata.created_at or datetime.now(timezone.utc)
            updated_at = entity.metadata.updated_at or created_at

            # Calculate age in days
            age_days = (datetime.now(timezone.utc) - created_at).days
            last_update_days = (datetime.now(timezone.utc) - updated_at).days

            # ONEX-inspired exponential decay scoring
            if age_days <= 30:
                age_score = 1.0  # 100% - very fresh
                age_reason = "very recent"
            elif age_days <= 90:
                age_score = 0.9  # 90% - recent
                age_reason = "recent"
            elif age_days <= 180:
                age_score = 0.7  # 70% - moderately fresh
                age_reason = "moderately fresh"
            elif age_days <= 365:
                age_score = 0.5  # 50% - aging
                age_reason = "aging"
            else:
                age_score = 0.3  # 30% - old
                age_reason = "old"

            # Enhanced update frequency scoring
            if last_update_days <= 7:
                update_multiplier = 1.1  # 10% bonus for very recent updates
                update_reason = "very recently updated"
            elif last_update_days <= 30:
                update_multiplier = 1.05  # 5% bonus for recent updates
                update_reason = "recently updated"
            elif last_update_days <= 90:
                update_multiplier = 1.0  # No penalty/bonus
                update_reason = "moderately updated"
            else:
                update_multiplier = 0.9  # 10% penalty for stale updates
                update_reason = "not recently updated"

            # Apply update frequency multiplier
            temporal_score = min(age_score * update_multiplier, 1.0)
            reason = (
                f"{age_reason} ({age_days}d), {update_reason} ({last_update_days}d ago)"
            )

            return temporal_score, reason

        except Exception as e:
            return 0.5, f"Temporal scoring error: {str(e)}"

    def _calculate_pattern_compliance(
        self, entity: KnowledgeEntity, content: str
    ) -> Tuple[float, str]:
        """Calculate pattern compliance score"""
        try:
            if not content:
                return 0.5, "No content for pattern analysis"

            good_pattern_score = 0.0
            bad_pattern_penalty = 0.0

            # Count good patterns
            good_patterns_found = []
            for pattern_regex, pattern_name, confidence in self.quality_patterns[
                "good_patterns"
            ]:
                if re.search(pattern_regex, content, re.DOTALL):
                    good_pattern_score += (
                        confidence * 0.1
                    )  # Scale down individual contributions
                    good_patterns_found.append(pattern_name)

            # Count bad patterns (code smells and security issues)
            bad_patterns_found = []
            for pattern_category in ["code_smells", "security_patterns"]:
                for pattern_regex, pattern_name, penalty in self.quality_patterns[
                    pattern_category
                ]:
                    if re.search(pattern_regex, content, re.DOTALL):
                        bad_pattern_penalty += abs(penalty) * 0.1
                        bad_patterns_found.append(pattern_name)

            # Calculate final score
            pattern_score = max(
                0.0, min(1.0, 0.5 + good_pattern_score - bad_pattern_penalty)
            )

            # Generate reason
            reason_parts = []
            if good_patterns_found:
                reason_parts.append(f"+{len(good_patterns_found)} good patterns")
            if bad_patterns_found:
                reason_parts.append(f"-{len(bad_patterns_found)} issues")

            reason = f"Pattern compliance: {', '.join(reason_parts) if reason_parts else 'neutral'}"

            return pattern_score, reason

        except Exception as e:
            return 0.5, f"Pattern compliance error: {str(e)}"

    def _calculate_cyclomatic_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity of code"""
        try:
            # Count decision points: if, elif, while, for, and, or, try, except
            decision_points = (
                len(re.findall(r"\bif\b", content))
                + len(re.findall(r"\belif\b", content))
                + len(re.findall(r"\bwhile\b", content))
                + len(re.findall(r"\bfor\b", content))
                + len(re.findall(r"\band\b", content))
                + len(re.findall(r"\bor\b", content))
                + len(re.findall(r"\btry\b", content))
                + len(re.findall(r"\bexcept\b", content))
            )

            # Cyclomatic complexity = decision points + 1
            return max(1, decision_points + 1)

        except Exception:
            return 1

    def _calculate_cognitive_complexity(self, content: str) -> int:
        """Calculate cognitive complexity (simplified approximation)"""
        try:
            # Nested structures add to cognitive load
            nesting_score = (
                len(re.findall(r"\bif\b.*?\bif\b", content)) * 2
                + len(re.findall(r"\bfor\b.*?\bfor\b", content)) * 2
                + len(re.findall(r"\bwhile\b.*?\bwhile\b", content)) * 2
                + len(re.findall(r"\btry\b.*?\btry\b", content)) * 2
            )

            # Base complexity from decision points
            base_complexity = self._calculate_cyclomatic_complexity(content)

            return base_complexity + nesting_score

        except Exception:
            return 1

    def _detect_function_patterns(
        self, content: str, entity: KnowledgeEntity
    ) -> List[PatternMatch]:
        """Detect function-specific patterns"""
        patterns = []

        # Long function detection
        lines = len(content.split("\n"))
        if lines > self.complexity_thresholds["max_lines_function"]:
            patterns.append(
                PatternMatch(
                    pattern_name="long_function",
                    pattern_type="code_smell",
                    confidence=0.8,
                    description=f"Function is too long ({lines} lines)",
                    severity="warning",
                    recommendation="Consider breaking into smaller functions",
                )
            )

        # Too many parameters
        param_matches = re.search(r"def\s+\w+\(([^)]+)\)", content)
        if param_matches:
            params = [p.strip() for p in param_matches.group(1).split(",") if p.strip()]
            if len(params) > 5:
                patterns.append(
                    PatternMatch(
                        pattern_name="too_many_parameters",
                        pattern_type="code_smell",
                        confidence=0.7,
                        description=f"Function has many parameters ({len(params)})",
                        severity="warning",
                        recommendation="Consider using a configuration object or reducing parameters",
                    )
                )

        return patterns

    def _detect_class_patterns(
        self, content: str, entity: KnowledgeEntity
    ) -> List[PatternMatch]:
        """Detect class-specific patterns"""
        patterns = []

        # Large class detection
        lines = len(content.split("\n"))
        if lines > self.complexity_thresholds["max_lines_class"]:
            patterns.append(
                PatternMatch(
                    pattern_name="large_class",
                    pattern_type="code_smell",
                    confidence=0.8,
                    description=f"Class is too large ({lines} lines)",
                    severity="warning",
                    recommendation="Consider splitting into multiple classes",
                )
            )

        # God class detection (too many methods)
        methods = len(re.findall(r"def\s+\w+", content))
        if methods > 20:
            patterns.append(
                PatternMatch(
                    pattern_name="god_class",
                    pattern_type="code_smell",
                    confidence=0.9,
                    description=f"Class has too many methods ({methods})",
                    severity="error",
                    recommendation="Break down into smaller, more focused classes",
                )
            )

        return patterns

    def _get_smell_recommendation(self, pattern_name: str) -> str:
        """Get recommendation for code smell patterns"""
        recommendations = {
            "long_parameter_list": "Use a configuration object or builder pattern",
            "deep_conditional": "Extract methods or use polymorphism",
            "nested_loops": "Extract inner loops into separate methods",
            "global_variable": "Pass variables as parameters or use dependency injection",
            "exec_usage": "Use safer alternatives like importlib or specific parsing",
            "eval_usage": "Use ast.literal_eval for safe evaluation or avoid altogether",
            "wildcard_import": "Import specific names or use qualified imports",
        }
        return recommendations.get(pattern_name, "Review and refactor this pattern")

    def _get_security_recommendation(self, pattern_name: str) -> str:
        """Get recommendation for security patterns"""
        recommendations = {
            "hardcoded_password": "Use environment variables or secure vaults",
            "hardcoded_api_key": "Use environment variables or configuration files",
            "sql_concatenation": "Use parameterized queries or ORM",
            "pickle_usage": "Use safer serialization formats like JSON",
            "subprocess_usage": "Validate inputs and use safer alternatives",
        }
        return recommendations.get(pattern_name, "Review security implications")

    def _calculate_architectural_compliance(
        self, entity: KnowledgeEntity, content: str
    ) -> Tuple[float, str]:
        """Calculate architectural compliance score based on ONEX patterns"""
        try:
            if not content:
                return 0.5, "No content for architectural analysis"

            # Null safety: ensure architectural_patterns is initialized
            if (
                not hasattr(self, "architectural_patterns")
                or self.architectural_patterns is None
            ):
                logger.warning(
                    "architectural_patterns not initialized, using default score"
                )
                return 0.5, "Architectural patterns not initialized"

            # Start with base score
            arch_score = 0.7
            issues_found = []
            patterns_found = []

            # Check for critical architectural failures (auto-fail patterns)
            critical_failures = self.architectural_patterns.get("critical_failures", [])
            for pattern_regex, pattern_name, description in critical_failures:
                if re.search(pattern_regex, content, re.MULTILINE):
                    arch_score = 0.0  # Critical failure = automatic low score
                    issues_found.append(f"CRITICAL: {description}")
                    return arch_score, f"Critical architectural failure: {description}"

            # Check for moderate issues (penalty scoring)
            moderate_issues = self.architectural_patterns.get("moderate_issues", [])
            for pattern_regex, pattern_name, description in moderate_issues:
                if re.search(pattern_regex, content, re.MULTILINE):
                    arch_score -= 0.2  # Penalty for each issue
                    issues_found.append(f"Issue: {description}")

            # Check for modern patterns (bonus scoring)
            modern_patterns = self.architectural_patterns.get("modern_patterns", [])
            for pattern_regex, pattern_name, description in modern_patterns:
                if re.search(pattern_regex, content, re.MULTILINE):
                    arch_score += 0.1  # Bonus for good patterns
                    patterns_found.append(f"Good: {description}")

            # Determine architectural era and apply modifier with null safety
            era_modifier = self._determine_architectural_era(content)
            if era_modifier is not None and isinstance(era_modifier, dict):
                arch_score += era_modifier.get("score_modifier", 0.0)
            else:
                logger.warning(
                    "era_modifier returned None or invalid type, skipping era adjustment"
                )

            # Clamp score to [0, 1]
            arch_score = max(0.0, min(1.0, arch_score))

            # Generate reason with null safety
            reason_parts = []
            if era_modifier is not None and isinstance(era_modifier, dict):
                era_name = era_modifier.get("era")
                if era_name:
                    reason_parts.append(f"Era: {era_name}")
            if patterns_found:
                reason_parts.append(f"+{len(patterns_found)} modern patterns")
            if issues_found:
                reason_parts.append(f"-{len(issues_found)} issues")

            reason = f"Architectural compliance: {', '.join(reason_parts) if reason_parts else 'neutral'}"

            return arch_score, reason

        except Exception as e:
            logger.error(
                f"Architectural compliance calculation error: {e}", exc_info=True
            )
            return 0.5, f"Architectural compliance error: {str(e)}"

    def _determine_architectural_era(self, content: str) -> Dict[str, Any]:
        """Determine which architectural era this code belongs to"""
        try:
            # Null safety: ensure architectural_eras is initialized
            if (
                not hasattr(self, "architectural_eras")
                or self.architectural_eras is None
            ):
                logger.warning("architectural_eras not initialized, using default era")
                return {"era": "modern_archon", "score_modifier": 0.0}

            # Null safety: ensure content is not None
            if content is None:
                return {"era": "modern_archon", "score_modifier": 0.0}

            for era_name, era_config in self.architectural_eras.items():
                # Null safety: ensure era_config is a dict and has required keys
                if not isinstance(era_config, dict):
                    continue

                patterns = era_config.get("patterns", [])
                if not patterns:
                    continue

                for pattern in patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        return {
                            "era": era_name,
                            "score_modifier": era_config.get("score_modifier", 0.0),
                        }

            # Default to modern if no specific patterns found
            return {"era": "modern_archon", "score_modifier": 0.0}

        except Exception as e:
            logger.error(f"Error determining architectural era: {e}", exc_info=True)
            # Always return a valid dict, never None
            return {"era": "unknown", "score_modifier": 0.0}
