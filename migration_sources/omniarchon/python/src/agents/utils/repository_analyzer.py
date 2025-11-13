#!/usr/bin/env python3
"""
Repository Analysis Utilities

Handles repository context establishment, technology stack detection,
and generation of insights and recommendations.

Version: 1.0.0
Author: Archon Intelligence Services
"""

import subprocess
from pathlib import Path
from typing import Any


class RepositoryAnalyzer:
    """
    Repository context and analysis engine.

    Provides repository context establishment, technology detection,
    quality analysis, and actionable recommendations generation.
    """

    def __init__(self):
        """Initialize repository analyzer."""
        self.verbose = False

    async def establish_repository_context(self, repo_path: Path) -> dict[str, Any]:
        """
        Establish comprehensive repository context.

        Args:
            repo_path: Root path of repository

        Returns:
            Dictionary with repository context information
        """
        context = {
            "path": str(repo_path),
            "name": repo_path.name,
            "files_count": 0,
            "git_info": {},
            "technology_stack": [],
        }

        # Get basic file count
        try:
            context["files_count"] = sum(
                1
                for _ in repo_path.rglob("*")
                if _.is_file() and not self._is_excluded_path(_)
            )
        except OSError as e:
            if self.verbose:
                print(f"⚠️ Cannot count files: {e}")
            context["files_count"] = 0

        # Extract git information
        try:
            git_commands = {
                "branch": ["git", "branch", "--show-current"],
                "commit": ["git", "rev-parse", "--short", "HEAD"],
                "remote": ["git", "remote", "get-url", "origin"],
            }

            for key, cmd in git_commands.items():
                try:
                    result = subprocess.run(
                        cmd, cwd=repo_path, capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        context["git_info"][key] = result.stdout.strip()
                except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                    if self.verbose:
                        print(f"⚠️ Git command '{key}' failed: {e}")
                    context["git_info"][key] = "unknown"

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Git info extraction failed: {e}")

        # Detect technology stack
        tech_indicators = {
            "package.json": "JavaScript/Node.js",
            "pyproject.toml": "Python/Poetry",
            "requirements.txt": "Python/pip",
            "Cargo.toml": "Rust",
            "pom.xml": "Java/Maven",
            "go.mod": "Go",
            "composer.json": "PHP",
            "Dockerfile": "Docker",
        }

        for file_name, tech in tech_indicators.items():
            if (repo_path / file_name).exists():
                context["technology_stack"].append(tech)

        return context

    async def generate_repository_insights(
        self,
        processed_files: list[dict[str, Any]],
        context: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate repository-level intelligence insights.

        Args:
            processed_files: List of processed file dictionaries
            context: Repository context dictionary
            config: Processing configuration

        Returns:
            Dictionary with repository insights
        """
        insights = {
            "summary": {},
            "quality_analysis": {},
            "technology_analysis": {},
            "documentation_analysis": {},
            "architecture_patterns": {},
            "recommendations": [],
        }

        # Summary statistics
        insights["summary"] = {
            "total_files_processed": len(processed_files),
            "files_with_intelligence": sum(
                1 for f in processed_files if f.get("intelligence_analysis")
            ),
            "file_types": {},
            "languages": {},
            "average_file_size": (
                sum(f["file_info"]["size"] for f in processed_files)
                / len(processed_files)
                if processed_files
                else 0
            ),
        }

        # Analyze file type distribution
        for file_data in processed_files:
            file_type = file_data["file_info"]["file_type"]
            language = file_data["file_info"]["language"]

            insights["summary"]["file_types"][file_type] = (
                insights["summary"]["file_types"].get(file_type, 0) + 1
            )
            insights["summary"]["languages"][language] = (
                insights["summary"]["languages"].get(language, 0) + 1
            )

        # Quality analysis from intelligence results
        code_files = [
            f for f in processed_files if f["file_info"]["file_type"] == "code"
        ]
        if code_files:
            quality_scores = []
            for file_data in code_files:
                intelligence = file_data.get("intelligence_analysis", {})
                if intelligence and intelligence.get("type") == "code_analysis":
                    service_result = intelligence.get("service_result", {})
                    if "quality_score" in service_result:
                        quality_scores.append(service_result["quality_score"])

            if quality_scores:
                insights["quality_analysis"] = {
                    "average_quality_score": sum(quality_scores) / len(quality_scores),
                    "quality_distribution": {
                        "high": sum(1 for s in quality_scores if s > 0.8)
                        / len(quality_scores),
                        "medium": sum(1 for s in quality_scores if 0.5 <= s <= 0.8)
                        / len(quality_scores),
                        "low": sum(1 for s in quality_scores if s < 0.5)
                        / len(quality_scores),
                    },
                    "files_analyzed": len(quality_scores),
                }

        # Technology analysis
        primary_languages = sorted(
            insights["summary"]["languages"].items(), key=lambda x: x[1], reverse=True
        )
        insights["technology_analysis"] = {
            "primary_language": (
                primary_languages[0][0] if primary_languages else "unknown"
            ),
            "language_diversity": len(insights["summary"]["languages"]),
            "technology_stack": context.get("technology_stack", []),
            "repository_classification": self._classify_repository(
                insights["summary"], context
            ),
        }

        # Documentation analysis
        doc_files = [
            f for f in processed_files if f["file_info"]["file_type"] == "documentation"
        ]
        insights["documentation_analysis"] = {
            "documentation_files": len(doc_files),
            "docs_to_code_ratio": len(doc_files) / max(len(code_files), 1),
            "has_readme": any(
                "readme" in f["file_info"]["name"].lower() for f in doc_files
            ),
            "documentation_coverage": (
                "good" if len(doc_files) / max(len(code_files), 1) > 0.2 else "limited"
            ),
        }

        return insights

    async def generate_recommendations(
        self, insights: dict[str, Any], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate actionable recommendations based on analysis.

        Args:
            insights: Repository insights dictionary
            config: Processing configuration

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # Quality-based recommendations
        quality_analysis = insights.get("quality_analysis", {})
        if quality_analysis:
            avg_quality = quality_analysis.get("average_quality_score", 0.5)
            if avg_quality < 0.6:
                recommendations.append(
                    {
                        "type": "quality_improvement",
                        "priority": "high",
                        "title": "Code Quality Improvement Needed",
                        "description": f"Average code quality score is {avg_quality:.2f}. Consider code refactoring and quality improvements.",
                        "action_items": [
                            "Review code with lowest quality scores",
                            "Implement code quality tools (linters, formatters)",
                            "Add unit tests for critical functionality",
                        ],
                    }
                )

        # Documentation recommendations
        doc_analysis = insights.get("documentation_analysis", {})
        if doc_analysis.get("docs_to_code_ratio", 0) < 0.1:
            recommendations.append(
                {
                    "type": "documentation_improvement",
                    "priority": "medium",
                    "title": "Documentation Coverage Low",
                    "description": "Low documentation-to-code ratio detected. Consider improving documentation.",
                    "action_items": [
                        "Add README files for key components",
                        "Document API interfaces and public functions",
                        "Create architecture overview documentation",
                    ],
                }
            )

        if not doc_analysis.get("has_readme", False):
            recommendations.append(
                {
                    "type": "documentation_missing",
                    "priority": "medium",
                    "title": "Missing README File",
                    "description": "No README file found at repository root.",
                    "action_items": [
                        "Create comprehensive README.md",
                        "Include project description and setup instructions",
                        "Add usage examples and contribution guidelines",
                    ],
                }
            )

        # Technology-specific recommendations
        tech_analysis = insights.get("technology_analysis", {})
        if tech_analysis.get("language_diversity", 0) > 5:
            recommendations.append(
                {
                    "type": "architecture_review",
                    "priority": "low",
                    "title": "High Language Diversity",
                    "description": "Multiple programming languages detected. Consider architecture review.",
                    "action_items": [
                        "Review language choices for consistency",
                        "Consider consolidating similar functionality",
                        "Document technology stack decisions",
                    ],
                }
            )

        # Processing-based recommendations
        files_processed = insights["summary"]["total_files_processed"]
        files_with_intelligence = insights["summary"]["files_with_intelligence"]

        if files_with_intelligence / max(files_processed, 1) < 0.5:
            recommendations.append(
                {
                    "type": "intelligence_coverage",
                    "priority": "low",
                    "title": "Limited Intelligence Analysis Coverage",
                    "description": "Some files could not be analyzed by intelligence services.",
                    "action_items": [
                        "Check intelligence service availability",
                        "Review file formats for compatibility",
                        "Consider manual review of unanalyzed files",
                    ],
                }
            )

        return recommendations

    def _classify_repository(
        self, summary: dict[str, Any], context: dict[str, Any]
    ) -> str:
        """
        Classify repository type based on analysis.

        Args:
            summary: Summary statistics dictionary
            context: Repository context dictionary

        Returns:
            Repository classification string
        """
        languages = summary.get("languages", {})
        tech_stack = context.get("technology_stack", [])

        if not languages:
            return "documentation"

        primary_language = max(languages, key=languages.get)

        # Classification logic
        if "Python" in tech_stack or primary_language == "python":
            return "python_project"
        elif "JavaScript" in tech_stack or primary_language in [
            "javascript",
            "typescript",
        ]:
            return "javascript_project"
        elif "Java" in tech_stack or primary_language == "java":
            return "java_project"
        elif primary_language == "rust":
            return "rust_project"
        elif primary_language == "go":
            return "go_project"
        elif len(languages) > 3:
            return "multi_language_project"
        else:
            return f"{primary_language}_project"

    def _is_excluded_path(self, path: Path) -> bool:
        """
        Check if path should be excluded from file counting.

        Excludes common build artifacts, dependency directories, and cache folders
        by matching exact path components (directory names), not substrings.

        Examples:
            - /path/to/node_modules/file.js -> EXCLUDED (exact match)
            - /path/to/my_node_modules_backup/file.js -> INCLUDED (not exact match)
            - /path/to/venv/lib/python -> EXCLUDED (exact match)
            - /path/to/my_venv_config.py -> INCLUDED (venv is substring, not component)

        Args:
            path: Path to check

        Returns:
            True if path should be excluded, False otherwise
        """
        # Common build artifacts, dependencies, and cache directories
        # These should match as exact path components, not substrings
        exclude_patterns = {
            "node_modules",  # Node.js dependencies
            ".git",  # Git repository metadata
            "__pycache__",  # Python bytecode cache
            "venv",  # Python virtual environment (generic name)
            ".venv",  # Python virtual environment (hidden)
            "env",  # Alternative virtual environment name
            ".env",  # Alternative virtual environment name (hidden)
            "build",  # Build output directory
            "dist",  # Distribution/build artifacts
            ".pytest_cache",  # Pytest cache directory
            ".mypy_cache",  # MyPy type checker cache
            ".tox",  # Tox testing environment
            "target",  # Rust/Java build output
            ".idea",  # JetBrains IDE settings
            ".vscode",  # VS Code settings
            ".DS_Store",  # macOS metadata (though typically a file)
            "coverage",  # Coverage report directories
            ".coverage",  # Coverage data files
            "htmlcov",  # Coverage HTML reports
        }

        # Check if any path component (directory name) matches exclusion patterns exactly
        # This prevents false positives like excluding "rebuild_utils.py" due to "build"
        path_parts = path.parts
        return any(part in exclude_patterns for part in path_parts)
