"""
ONEX Quality Scoring Utility

Migrated from: omnibase_3/src/omnibase/tools/intelligence/.../onex_quality_scorer.py
Migration Date: 2025-10-14
Purpose: Code quality and ONEX compliance scoring for codegen validation
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class ONEXQualityScorer:
    """Analyzes content for ONEX compliance and calculates quality scores."""

    def __init__(self):
        # Critical legacy patterns (auto-reject: score = 0.0)
        self.critical_legacy_patterns = [
            r"from\s+typing\s+import\s+.*\bAny\b",  # Any types usage from typing
            r":\s*Any\b",  # Any type annotations
            r"class\s+[a-z]\w*\([^)]*BaseModel[^)]*\):",  # Non-CamelCase Pydantic models
            r"\b(Database|Connection|Client)\(\)",  # Direct instantiation of services
        ]

        # Moderate legacy patterns (score = 0.3-0.6)
        self.moderate_legacy_patterns = [
            r"class\s+[a-z]\w*:",  # Non-CamelCase class names
            r"def\s+\w+\([^)]*\)\s*:\s*\n\s*\w+\s*=\s*\w+\(",  # Direct instantiation in functions
            r"import\s+os",  # Direct OS imports (should use container)
            r"\.get\(",  # Dict .get() without proper typing
        ]

        # Modern ONEX patterns (score = 0.8-1.0)
        self.modern_onex_patterns = [
            r"def\s+__init__\(self,\s*registry:\s*\w+Registry\)",  # Registry injection
            r"class\s+Model[A-Z]\w*\(BaseModel\)",  # CamelCase Pydantic models
            r"from\s+omnibase\.protocols",  # Protocol usage
            r"@standard_error_handling",  # Proper error handling
            r"NodeBase",  # NodeBase integration
            r"OnexError",  # Proper exception handling
            r"contract_path\s*=\s*Path",  # Contract-driven patterns
            r"emit_log_event",  # ONEX logging
            r"ModelONEXContainer",  # Correct container class
            r"CoreErrorCode",  # Error code enum
            r"Node(Effect|Compute|Transform|Input|Output)",  # Node types
        ]

        # Architectural era indicators
        self.architectural_eras = {
            "pre_nodebase": [
                r"class\s+\w+Tool:",
                r"def\s+main\(\):\s*parser",
                r"argparse",
            ],
            "early_nodebase": [
                r"NodeBase\(",
                r"class\s+\w+\(NodeBase\)",
                r"__main__.*NodeBase",
            ],
            "contract_driven": [
                r"contract\.yaml",
                r"from_contract",
                r"CONTRACT_FILENAME",
            ],
            "modern_onex": [
                r"registry:\s*BaseOnexRegistry",
                r"container:\s*ModelONEXContainer",
                r"@standard_error_handling",
                r"ProtocolToolBase",
                r"emit_log_event",
                r"Model[A-Z]\w+",
            ],
        }

    def analyze_content(
        self,
        content: str,
        file_path: Optional[str] = None,
        file_last_modified: Optional[datetime] = None,
        git_commit_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Analyze content and return comprehensive quality metrics."""

        # Calculate ONEX compliance score
        onex_compliance_score = self._calculate_onex_compliance(content)

        # Calculate temporal relevance score
        relevance_score = self._calculate_temporal_relevance(
            file_last_modified, git_commit_date
        )

        # Detect architectural era
        architectural_era = self._detect_architectural_era(content)

        # Detect legacy indicators
        legacy_indicators = self._detect_legacy_indicators(content)

        # Calculate overall quality score
        quality_score = self._calculate_overall_quality(
            onex_compliance_score, relevance_score, architectural_era, legacy_indicators
        )

        return {
            "quality_score": quality_score,
            "relevance_score": relevance_score,
            "onex_compliance_score": onex_compliance_score,
            "architectural_era": architectural_era,
            "legacy_indicators": legacy_indicators,
            "file_last_modified": file_last_modified,
            "git_commit_date": git_commit_date,
        }

    def _calculate_onex_compliance(self, content: str) -> float:
        """Calculate ONEX architectural compliance score (0.0-1.0)."""
        score = 0.5  # Start with neutral score

        # Check for critical legacy patterns (auto-fail)
        # Note: Not using IGNORECASE so [a-z] only matches lowercase
        for pattern in self.critical_legacy_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return 0.0  # Critical failure

        # Deduct for moderate legacy patterns
        # Note: Not using IGNORECASE so [a-z] only matches lowercase
        legacy_penalty = 0.0
        for pattern in self.moderate_legacy_patterns:
            matches = len(re.findall(pattern, content, re.MULTILINE))
            legacy_penalty += matches * 0.1  # 0.1 penalty per match

        # Add points for modern ONEX patterns
        modern_bonus = 0.0
        for pattern in self.modern_onex_patterns:
            matches = len(re.findall(pattern, content, re.MULTILINE))
            modern_bonus += matches * 0.1  # 0.1 bonus per match

        # Calculate final score
        final_score = score - legacy_penalty + modern_bonus
        return max(0.0, min(1.0, final_score))

    def _calculate_temporal_relevance(
        self,
        file_last_modified: Optional[datetime],
        git_commit_date: Optional[datetime],
    ) -> float:
        """Calculate temporal relevance score (0.0-1.0) based on recency."""
        now = datetime.now(timezone.utc)

        # Use the most recent timestamp available
        reference_date = None
        if git_commit_date:
            reference_date = git_commit_date
        elif file_last_modified:
            reference_date = file_last_modified
        else:
            return 0.5  # Neutral score if no temporal data

        # Ensure timezone awareness
        if reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=timezone.utc)

        # Calculate days since last modification
        days_old = (now - reference_date).days

        # Scoring function: exponential decay
        # 100% for content < 30 days old
        # 90% for content < 90 days old
        # 70% for content < 180 days old
        # 50% for content < 365 days old
        # 30% for content older than 1 year
        if days_old <= 30:
            return 1.0
        elif days_old <= 90:
            return 0.9
        elif days_old <= 180:
            return 0.7
        elif days_old <= 365:
            return 0.5
        else:
            return 0.3

    def _detect_architectural_era(self, content: str) -> str:
        """Detect which ONEX architectural era the content belongs to."""
        era_scores = {}

        for era, patterns in self.architectural_eras.items():
            score = 0
            for pattern in patterns:
                matches = len(
                    re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                )
                score += matches
            era_scores[era] = score

        # Return era with highest score, default to modern if no clear match
        if not any(era_scores.values()):
            return "modern_onex"

        return max(era_scores.items(), key=lambda x: x[1])[0]

    def _detect_legacy_indicators(self, content: str) -> List[str]:
        """Detect specific legacy patterns in the content."""
        indicators = []

        # Map patterns to human-readable descriptions
        pattern_descriptions = {
            r"from\s+typing\s+import\s+.*\bAny\b": "Uses Any types (forbidden in ONEX)",
            r":\s*Any\b": "Uses Any type annotations (forbidden in ONEX)",
            r"class\s+[a-z]\w*\([^)]*BaseModel[^)]*\):": "Non-CamelCase Pydantic models (should be Model* prefix)",
            r"\b(Database|Connection|Client)\(\)": "Direct instantiation without container",
            r"class\s+[a-z]\w*:": "Non-CamelCase class names",
            r"import\s+os": "Direct OS imports (should use container)",
        }

        for pattern, description in pattern_descriptions.items():
            if re.search(pattern, content, re.MULTILINE):
                indicators.append(description)

        return indicators

    def _calculate_overall_quality(
        self,
        onex_compliance_score: float,
        relevance_score: float,
        architectural_era: str,
        legacy_indicators: List[str],
    ) -> float:
        """Calculate weighted overall quality score."""

        # Weighted average: compliance (60%), relevance (30%), era bonus (10%)
        base_score = (onex_compliance_score * 0.6) + (relevance_score * 0.3)

        # Architectural era bonus/penalty
        era_modifiers = {
            "pre_nodebase": -0.2,
            "early_nodebase": -0.1,
            "contract_driven": 0.05,
            "modern_onex": 0.1,
        }

        era_modifier = era_modifiers.get(architectural_era, 0)
        final_score = base_score + (era_modifier * 0.1)

        # Heavy penalty for critical legacy indicators
        if any("forbidden" in indicator.lower() for indicator in legacy_indicators):
            final_score *= 0.1  # 90% penalty for forbidden patterns

        return max(0.0, min(1.0, final_score))
