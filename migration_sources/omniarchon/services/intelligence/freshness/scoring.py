"""
Freshness Scoring Engine for Archon Document Analysis

Advanced freshness scoring algorithms using time decay, dependency analysis,
content relevance, and usage patterns to determine document freshness.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from .models import (
    Dependency,
    DocumentType,
    FreshnessLevel,
    FreshnessScore,
)

logger = logging.getLogger(__name__)


class FreshnessScorer:
    """
    Advanced freshness scoring engine with configurable algorithms
    and intelligent dependency-aware analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize scorer with configuration"""

        # Default configuration
        self.config = {
            # Time decay parameters
            "time_decay_half_life_days": 30,  # Half-life for time decay
            "max_age_critical_days": 365,  # Age threshold for critical staleness
            "recent_update_bonus_days": 7,  # Bonus for very recent updates
            # Dependency scoring
            "dependency_weight": 0.3,  # Weight of dependency score
            "critical_dependency_penalty": 0.2,  # Penalty for broken critical deps
            "dependency_freshness_threshold": 0.7,  # Threshold for fresh dependencies
            # Content analysis
            "content_relevance_weight": 0.2,  # Weight of content relevance
            "code_example_bonus": 0.1,  # Bonus for having code examples
            "link_penalty": 0.05,  # Penalty per broken link
            "outdated_version_penalty": 0.15,  # Penalty for outdated version refs
            # Usage patterns
            "usage_frequency_weight": 0.1,  # Weight of usage frequency
            "access_decay_days": 90,  # Decay period for access patterns
            # Document type specific adjustments
            "type_adjustments": {
                DocumentType.README: 0.9,  # READMEs are critical
                DocumentType.API_DOCUMENTATION: 0.8,  # API docs need to be current
                DocumentType.TUTORIAL: 0.7,  # Tutorials can be slightly older
                DocumentType.CHANGELOG: 1.0,  # Changelogs should be current
                DocumentType.TROUBLESHOOTING: 0.8,  # Troubleshooting should be current
                DocumentType.ARCHITECTURE: 0.6,  # Architecture docs more stable
                DocumentType.CONFIGURATION: 0.9,  # Config docs critical
                DocumentType.UNKNOWN: 0.5,  # Unknown docs lower priority
            },
            # Freshness level thresholds
            "freshness_thresholds": {
                FreshnessLevel.FRESH: 0.8,  # > 0.8 is fresh
                FreshnessLevel.STALE: 0.6,  # 0.6-0.8 is stale
                FreshnessLevel.OUTDATED: 0.3,  # 0.3-0.6 is outdated
                FreshnessLevel.CRITICAL: 0.0,  # < 0.3 is critical
            },
        }

        # Update with provided config
        if config:
            self._update_config(config)

        # Compile regex patterns for content analysis
        self._compile_patterns()

        logger.info("FreshnessScorer initialized with configuration")

    def _update_config(self, new_config: Dict[str, Any]):
        """Recursively update configuration"""

        def update_dict(base: dict, updates: dict):
            for key, value in updates.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    update_dict(base[key], value)
                else:
                    base[key] = value

        update_dict(self.config, new_config)

    def _compile_patterns(self):
        """Compile regex patterns for content analysis"""
        self.patterns = {
            # Version patterns
            "version_refs": re.compile(
                r"v?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?", re.IGNORECASE
            ),
            "outdated_versions": re.compile(
                r"python\s*[<>=]*\s*[23]\.\d+|node\s*[<>=]*\s*\d+", re.IGNORECASE
            ),
            # Link patterns
            "http_links": re.compile(r"https?://[^\s\)]+", re.IGNORECASE),
            "relative_links": re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
            # Code patterns
            "code_blocks": re.compile(r"```[\s\S]*?```|`[^`]+`"),
            "import_statements": re.compile(r"(?:from|import)\s+[\w\.]+", re.MULTILINE),
            # Temporal indicators
            "temporal_words": re.compile(
                r"\b(?:recently|currently|now|today|latest|new|updated|deprecated|legacy|old)\b",
                re.IGNORECASE,
            ),
            "date_patterns": re.compile(
                r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b"
            ),
        }

    async def calculate_freshness_score(
        self,
        document_path: str,
        content: str,
        last_modified: datetime,
        dependencies: List[Dependency],
        document_type: DocumentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FreshnessScore:
        """
        Calculate comprehensive freshness score for a document.

        Args:
            document_path: Path to the document
            content: Document content
            last_modified: Last modification time
            dependencies: List of document dependencies
            document_type: Classified document type
            metadata: Additional metadata (access patterns, etc.)

        Returns:
            Detailed freshness score
        """
        logger.debug(f"Calculating freshness score for {document_path}")

        # Calculate individual scoring components
        time_decay_score = await self._calculate_time_decay_score(last_modified)
        dependency_score = await self._calculate_dependency_score(dependencies)
        content_relevance_score = await self._calculate_content_relevance_score(
            content, document_type
        )
        usage_frequency_score = await self._calculate_usage_frequency_score(
            document_path, metadata
        )

        # Apply document type adjustment
        type_adjustment = self.config["type_adjustments"].get(document_type, 0.5)

        # Calculate weighted overall score
        weights = {
            "time": self.config.get("time_decay_weight", 0.4),
            "dependency": self.config["dependency_weight"],
            "content": self.config["content_relevance_weight"],
            "usage": self.config["usage_frequency_weight"],
        }

        # Ensure weights sum to 1.0
        total_weight = sum(weights.values())
        if total_weight != 1.0:
            for key in weights:
                weights[key] /= total_weight

        overall_score = (
            time_decay_score * weights["time"]
            + dependency_score * weights["dependency"]
            + content_relevance_score * weights["content"]
            + usage_frequency_score * weights["usage"]
        ) * type_adjustment

        # Ensure score is in valid range
        overall_score = max(0.0, min(1.0, overall_score))

        # Collect detailed factors
        factors = {
            "document_age_days": (datetime.now(timezone.utc) - last_modified).days,
            "type_adjustment": type_adjustment,
            "dependencies_count": len(dependencies),
            "broken_dependencies": len(
                [d for d in dependencies if d.verification_status == "broken"]
            ),
            "content_indicators": await self._analyze_content_indicators(content),
            "weighted_components": {
                "time_decay": time_decay_score * weights["time"],
                "dependency": dependency_score * weights["dependency"],
                "content_relevance": content_relevance_score * weights["content"],
                "usage_frequency": usage_frequency_score * weights["usage"],
            },
        }

        # Generate explanation
        explanation = self._generate_score_explanation(
            overall_score,
            time_decay_score,
            dependency_score,
            content_relevance_score,
            usage_frequency_score,
            document_type,
        )

        return FreshnessScore(
            overall_score=overall_score,
            time_decay_score=time_decay_score,
            dependency_score=dependency_score,
            content_relevance_score=content_relevance_score,
            usage_frequency_score=usage_frequency_score,
            time_weight=weights["time"],
            dependency_weight=weights["dependency"],
            content_weight=weights["content"],
            usage_weight=weights["usage"],
            factors=factors,
            explanation=explanation,
        )

    async def _calculate_time_decay_score(self, last_modified: datetime) -> float:
        """Calculate time-based freshness score with exponential decay"""
        age_days = (datetime.now(timezone.utc) - last_modified).days
        half_life = self.config["time_decay_half_life_days"]

        # Exponential decay: score = 0.5^(age_days / half_life)
        base_score = 0.5 ** (age_days / half_life)

        # Apply recent update bonus
        recent_bonus_days = self.config["recent_update_bonus_days"]
        if age_days <= recent_bonus_days:
            # Linear bonus for very recent updates
            bonus = (recent_bonus_days - age_days) / recent_bonus_days * 0.1
            base_score = min(1.0, base_score + bonus)

        # Critical age penalty
        critical_age = self.config["max_age_critical_days"]
        if age_days >= critical_age:
            base_score *= 0.5  # Significant penalty for very old docs

        return max(0.0, min(1.0, base_score))

    async def _calculate_dependency_score(
        self, dependencies: List[Dependency]
    ) -> float:
        """Calculate score based on dependency freshness and health"""
        if not dependencies:
            return 1.0  # No dependencies = no dependency issues

        total_score = 0.0
        critical_penalty = 0.0

        for dep in dependencies:
            # Base score for this dependency
            dep_score = 1.0

            # Check verification status
            if dep.verification_status == "broken":
                dep_score *= 0.3  # Significant penalty for broken deps
                if dep.is_critical:
                    critical_penalty += self.config["critical_dependency_penalty"]
            elif dep.verification_status == "outdated":
                dep_score *= 0.6  # Moderate penalty for outdated deps
            elif dep.verification_status == "unverified":
                dep_score *= 0.8  # Small penalty for unverified

            # Consider dependency age
            dep_age_days = (datetime.now(timezone.utc) - dep.last_verified).days
            if dep_age_days > 90:  # Haven't verified in 3 months
                dep_score *= 0.7

            total_score += dep_score

        # Average score across all dependencies
        avg_score = total_score / len(dependencies)

        # Apply critical dependency penalty
        final_score = max(0.0, avg_score - critical_penalty)

        return min(1.0, final_score)

    async def _calculate_content_relevance_score(
        self, content: str, document_type: DocumentType
    ) -> float:
        """Calculate score based on content analysis and relevance indicators"""
        base_score = 0.7  # Neutral starting point

        # Analyze content indicators
        indicators = await self._analyze_content_indicators(content)

        # Positive indicators
        if indicators["has_recent_dates"]:
            base_score += 0.1

        if indicators["has_code_examples"] and document_type in [
            DocumentType.TUTORIAL,
            DocumentType.API_DOCUMENTATION,
            DocumentType.GUIDE,
        ]:
            base_score += self.config["code_example_bonus"]

        if indicators["temporal_freshness_words"] > 0:
            # Words like "recently", "updated", "new"
            base_score += min(0.1, indicators["temporal_freshness_words"] * 0.02)

        if indicators["temporal_staleness_words"] > 0:
            # Words like "deprecated", "legacy", "old"
            base_score -= min(0.2, indicators["temporal_staleness_words"] * 0.05)

        # Version reference analysis
        if indicators["has_outdated_versions"]:
            base_score -= self.config["outdated_version_penalty"]

        # Link analysis penalty
        if indicators["broken_links_estimated"] > 0:
            link_penalty = (
                indicators["broken_links_estimated"] * self.config["link_penalty"]
            )
            base_score -= min(0.3, link_penalty)

        # Document completeness indicators
        if indicators["appears_incomplete"]:
            base_score -= 0.15

        if indicators["has_todo_sections"]:
            base_score -= 0.1

        return max(0.0, min(1.0, base_score))

    async def _calculate_usage_frequency_score(
        self, document_path: str, metadata: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate score based on usage patterns and access frequency"""
        # Default score when no usage data available
        if not metadata or "access_patterns" not in metadata:
            return 0.5

        access_patterns = metadata["access_patterns"]

        # Get recent access data
        recent_accesses = access_patterns.get("last_30_days", 0)
        access_patterns.get("total_accesses", 0)
        last_accessed = access_patterns.get("last_accessed")

        # Calculate recency score
        if last_accessed:
            days_since_access = (datetime.now(timezone.utc) - last_accessed).days
            decay_period = self.config["access_decay_days"]
            recency_score = max(0.0, 1.0 - (days_since_access / decay_period))
        else:
            recency_score = 0.0

        # Calculate frequency score
        if recent_accesses > 0:
            # Logarithmic scaling for frequency
            frequency_score = min(1.0, np.log(recent_accesses + 1) / np.log(100))
        else:
            frequency_score = 0.0

        # Combine recency and frequency
        usage_score = (recency_score * 0.6) + (frequency_score * 0.4)

        return max(0.0, min(1.0, usage_score))

    async def _analyze_content_indicators(self, content: str) -> Dict[str, Any]:
        """Analyze content for various freshness indicators"""
        indicators = {
            "has_recent_dates": False,
            "has_outdated_versions": False,
            "has_code_examples": False,
            "has_links": False,
            "broken_links_estimated": 0,
            "temporal_freshness_words": 0,
            "temporal_staleness_words": 0,
            "appears_incomplete": False,
            "has_todo_sections": False,
            "version_references": [],
        }

        # Analyze dates
        date_matches = self.patterns["date_patterns"].findall(content)
        if date_matches:
            # Check if any dates are recent (within last year)
            current_year = datetime.now(timezone.utc).year
            for date_str in date_matches:
                if str(current_year) in date_str or str(current_year - 1) in date_str:
                    indicators["has_recent_dates"] = True
                    break

        # Analyze version references
        version_matches = self.patterns["version_refs"].findall(content)
        indicators["version_references"] = version_matches

        # Check for potentially outdated versions
        outdated_matches = self.patterns["outdated_versions"].findall(content)
        indicators["has_outdated_versions"] = len(outdated_matches) > 0

        # Count code examples
        code_matches = self.patterns["code_blocks"].findall(content)
        indicators["has_code_examples"] = len(code_matches) > 0

        # Analyze links
        link_matches = self.patterns["http_links"].findall(content)
        indicators["has_links"] = len(link_matches) > 0
        # Estimate broken links (placeholder - would need actual HTTP checks)
        indicators["broken_links_estimated"] = max(0, len(link_matches) // 10)

        # Count temporal words
        freshness_words = [
            "recently",
            "currently",
            "now",
            "today",
            "latest",
            "new",
            "updated",
        ]
        staleness_words = ["deprecated", "legacy", "old", "obsolete", "discontinued"]

        content_lower = content.lower()
        for word in freshness_words:
            indicators["temporal_freshness_words"] += content_lower.count(word)

        for word in staleness_words:
            indicators["temporal_staleness_words"] += content_lower.count(word)

        # Check for incomplete content indicators
        incomplete_indicators = ["todo", "fixme", "tbd", "coming soon", "[placeholder]"]
        for indicator in incomplete_indicators:
            if indicator in content_lower:
                indicators["appears_incomplete"] = True
                break

        # Check for TODO sections
        indicators["has_todo_sections"] = "todo" in content_lower and (
            "##" in content or "###" in content
        )

        return indicators

    def _generate_score_explanation(
        self,
        overall_score: float,
        time_score: float,
        dependency_score: float,
        content_score: float,
        usage_score: float,
        document_type: DocumentType,
    ) -> str:
        """Generate human-readable explanation of the freshness score"""

        explanations = []

        # Overall assessment
        if overall_score >= 0.8:
            explanations.append("Document appears fresh and well-maintained.")
        elif overall_score >= 0.6:
            explanations.append(
                "Document shows some signs of staleness but is generally usable."
            )
        elif overall_score >= 0.3:
            explanations.append("Document is outdated and likely needs attention.")
        else:
            explanations.append(
                "Document is critically stale and may contain incorrect information."
            )

        # Time component
        if time_score >= 0.8:
            explanations.append("Recently updated content.")
        elif time_score >= 0.5:
            explanations.append("Moderately aged content.")
        else:
            explanations.append("Old content that hasn't been updated in a while.")

        # Dependencies
        if dependency_score >= 0.8:
            explanations.append("Dependencies appear healthy.")
        elif dependency_score >= 0.5:
            explanations.append("Some dependency issues detected.")
        else:
            explanations.append("Significant dependency problems found.")

        # Content analysis
        if content_score >= 0.7:
            explanations.append("Content appears current and relevant.")
        elif content_score >= 0.5:
            explanations.append("Content has some outdated elements.")
        else:
            explanations.append("Content shows clear signs of being outdated.")

        # Usage patterns
        if usage_score >= 0.7:
            explanations.append("Frequently accessed document.")
        elif usage_score >= 0.3:
            explanations.append("Moderate usage patterns.")
        else:
            explanations.append("Low usage document.")

        # Document type context
        type_context = {
            DocumentType.README: "READMEs should be kept very current as they're often the first impression.",
            DocumentType.API_DOCUMENTATION: "API documentation needs frequent updates to reflect changes.",
            DocumentType.TUTORIAL: "Tutorials benefit from regular updates but can tolerate some age.",
            DocumentType.ARCHITECTURE: "Architecture documents tend to be more stable over time.",
        }

        if document_type in type_context:
            explanations.append(type_context[document_type])

        return " ".join(explanations)

    def determine_freshness_level(self, score: float) -> FreshnessLevel:
        """Determine freshness level based on score and thresholds"""
        thresholds = self.config["freshness_thresholds"]

        if score >= thresholds[FreshnessLevel.FRESH]:
            return FreshnessLevel.FRESH
        elif score >= thresholds[FreshnessLevel.STALE]:
            return FreshnessLevel.STALE
        elif score >= thresholds[FreshnessLevel.OUTDATED]:
            return FreshnessLevel.OUTDATED
        else:
            return FreshnessLevel.CRITICAL
