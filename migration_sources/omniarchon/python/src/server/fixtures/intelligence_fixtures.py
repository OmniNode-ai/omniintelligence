"""
Intelligence Data Fixtures

Reusable test data and mock objects for intelligence system testing and debugging.
Provides realistic correlation data, file structures, and ASCII visualization tools.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class MockDocument:
    """Mock intelligence document for testing."""

    id: str
    repository: str
    commit_sha: str
    created_at: str
    modified_files: list[str]
    content: str


class IntelligenceFixtures:
    """Collection of reusable intelligence test fixtures."""

    @staticmethod
    def get_mock_documents() -> list[MockDocument]:
        """Get realistic mock documents with varied file structures."""
        base_time = datetime.now(UTC)

        return [
            MockDocument(
                id="doc-python-api",
                repository="omniagent",
                commit_sha="abc123def456",
                created_at=(base_time - timedelta(hours=2)).isoformat(),
                modified_files=[
                    "src/api/endpoints.py",
                    "src/models/user.py",
                    "tests/test_api.py",
                    "tests/test_models.py",
                    "requirements.txt",
                    "pyproject.toml",
                    "README.md",
                ],
                content="FastAPI endpoint implementation with Pydantic models, comprehensive pytest testing, and SQLAlchemy database integration",
            ),
            MockDocument(
                id="doc-react-ui",
                repository="archon-ui",
                commit_sha="xyz789abc123",
                created_at=(base_time - timedelta(hours=1)).isoformat(),
                modified_files=[
                    "src/components/Dashboard.tsx",
                    "src/components/IntelligenceTable.tsx",
                    "src/pages/Intelligence.tsx",
                    "src/hooks/useIntelligence.ts",
                    "src/styles/globals.css",
                    "src/types/intelligence.ts",
                    "package.json",
                    "tsconfig.json",
                    "tailwind.config.js",
                ],
                content="React TypeScript dashboard components with Tailwind CSS styling, custom hooks for data fetching, and comprehensive TypeScript type definitions",
            ),
            MockDocument(
                id="doc-rust-mcp",
                repository="omnimcp",
                commit_sha="def456ghi789",
                created_at=(base_time - timedelta(minutes=30)).isoformat(),
                modified_files=[
                    "src/main.rs",
                    "src/lib.rs",
                    "src/handlers/mod.rs",
                    "src/models/protocol.rs",
                    "Cargo.toml",
                    "Cargo.lock",
                    "README.md",
                    ".github/workflows/ci.yml",
                ],
                content="Rust MCP server implementation with async tokio runtime, protocol message handlers, structured logging with tracing, and comprehensive CI/CD pipeline",
            ),
            MockDocument(
                id="doc-python-agents",
                repository="claude-toolkit",
                commit_sha="ghi789jkl012",
                created_at=base_time.isoformat(),
                modified_files=[
                    "src/tools/search.py",
                    "src/agents/base.py",
                    "src/agents/specialized.py",
                    "src/utils/validation.py",
                    "config/settings.yaml",
                    "config/agent_configs.yaml",
                    "docker-compose.yml",
                    "Dockerfile",
                    "tests/test_agents.py",
                ],
                content="Python agent toolkit with YAML configuration, Docker deployment, specialized agent implementations, comprehensive validation utilities, and extensive testing suite",
            ),
            MockDocument(
                id="doc-go-microservice",
                repository="message-service",
                commit_sha="mno345pqr678",
                created_at=(base_time - timedelta(minutes=45)).isoformat(),
                modified_files=[
                    "cmd/server/main.go",
                    "internal/handler/message.go",
                    "internal/models/message.go",
                    "internal/database/postgres.go",
                    "pkg/validation/validator.go",
                    "go.mod",
                    "go.sum",
                    "Dockerfile",
                    "k8s/deployment.yaml",
                ],
                content="Go microservice for message processing with PostgreSQL database, comprehensive validation, Docker containerization, and Kubernetes deployment manifests",
            ),
            MockDocument(
                id="doc-vue-frontend",
                repository="admin-dashboard",
                commit_sha="stu901vwx234",
                created_at=(base_time - timedelta(hours=3)).isoformat(),
                modified_files=[
                    "src/views/Dashboard.vue",
                    "src/components/MetricsCard.vue",
                    "src/composables/useMetrics.ts",
                    "src/stores/dashboard.ts",
                    "src/router/index.ts",
                    "src/assets/styles/dashboard.scss",
                    "package.json",
                    "vite.config.ts",
                    "tailwind.config.js",
                ],
                content="Vue 3 admin dashboard with Composition API, Pinia state management, custom composables for metrics, SCSS styling with Tailwind CSS, and Vite build tooling",
            ),
        ]

    @staticmethod
    def get_realistic_correlations() -> dict[str, Any]:
        """Get realistic correlation data with proper file information."""
        return {
            "temporal_correlations": [
                {
                    "repository": "archon-ui",
                    "commit_sha": "xyz789abc123",
                    "time_diff_hours": 1.0,
                    "correlation_strength": 0.67,
                },
                {
                    "repository": "omnimcp",
                    "commit_sha": "def456ghi789",
                    "time_diff_hours": 1.5,
                    "correlation_strength": 0.45,
                },
                {
                    "repository": "message-service",
                    "commit_sha": "mno345pqr678",
                    "time_diff_hours": 0.75,
                    "correlation_strength": 0.82,
                },
            ],
            "semantic_correlations": [
                {
                    "repository": "archon-ui",
                    "commit_sha": "xyz789abc123",
                    "semantic_similarity": 0.72,
                    "common_keywords": [
                        "dashboard",
                        "react",
                        "typescript",
                        "components",
                        "hooks",
                    ],
                    "file_information": {
                        "common_files": ["package.json", "tsconfig.json", "README.md"],
                        "common_extensions": ["tsx", "ts", "json", "css", "js"],
                        "common_directories": ["src", "src/components", "src/pages"],
                        "file_overlap_ratio": 0.35,
                        "technology_stack": [
                            "React",
                            "TypeScript",
                            "Tailwind CSS",
                            "Vite",
                        ],
                    },
                },
                {
                    "repository": "omnimcp",
                    "commit_sha": "def456ghi789",
                    "semantic_similarity": 0.58,
                    "common_keywords": [
                        "server",
                        "async",
                        "protocol",
                        "handlers",
                        "mcp",
                    ],
                    "file_information": {
                        "common_files": ["README.md", "Cargo.toml"],
                        "common_extensions": ["rs", "toml", "yml", "md"],
                        "common_directories": [
                            "src",
                            "src/handlers",
                            "src/models",
                            ".github",
                        ],
                        "file_overlap_ratio": 0.28,
                        "technology_stack": ["Rust", "Tokio", "MCP Protocol", "CI/CD"],
                    },
                },
                {
                    "repository": "claude-toolkit",
                    "commit_sha": "ghi789jkl012",
                    "semantic_similarity": 0.84,
                    "common_keywords": [
                        "python",
                        "agents",
                        "tools",
                        "validation",
                        "testing",
                    ],
                    "file_information": {
                        "common_files": [
                            "docker-compose.yml",
                            "Dockerfile",
                            "README.md",
                        ],
                        "common_extensions": ["py", "yaml", "yml", "txt"],
                        "common_directories": [
                            "src",
                            "config",
                            "tests",
                            "src/agents",
                            "src/tools",
                        ],
                        "file_overlap_ratio": 0.42,
                        "technology_stack": [
                            "Python",
                            "Docker",
                            "YAML",
                            "Testing",
                            "Agents",
                        ],
                    },
                },
                {
                    "repository": "message-service",
                    "commit_sha": "mno345pqr678",
                    "semantic_similarity": 0.31,
                    "common_keywords": ["go", "microservice", "database", "validation"],
                    "file_information": {
                        "common_files": ["go.mod", "Dockerfile"],
                        "common_extensions": ["go", "yaml", "sum", "md"],
                        "common_directories": ["cmd", "internal", "pkg", "k8s"],
                        "file_overlap_ratio": 0.15,
                        "technology_stack": [
                            "Go",
                            "PostgreSQL",
                            "Docker",
                            "Kubernetes",
                        ],
                    },
                },
                {
                    "repository": "admin-dashboard",
                    "commit_sha": "stu901vwx234",
                    "semantic_similarity": 0.69,
                    "common_keywords": [
                        "vue",
                        "dashboard",
                        "composables",
                        "pinia",
                        "metrics",
                    ],
                    "file_information": {
                        "common_files": ["package.json", "tailwind.config.js"],
                        "common_extensions": ["vue", "ts", "scss", "js", "json"],
                        "common_directories": [
                            "src",
                            "src/views",
                            "src/components",
                            "src/composables",
                        ],
                        "file_overlap_ratio": 0.33,
                        "technology_stack": [
                            "Vue 3",
                            "TypeScript",
                            "Pinia",
                            "SCSS",
                            "Tailwind",
                            "Vite",
                        ],
                    },
                },
            ],
            "breaking_changes": [
                {
                    "type": "api_change",
                    "severity": "medium",
                    "description": "Modified API endpoint signature for user authentication",
                    "files_affected": ["src/api/endpoints.py", "src/models/user.py"],
                },
                {
                    "type": "dependency_update",
                    "severity": "low",
                    "description": "Updated major dependency versions with potential compatibility issues",
                    "files_affected": ["package.json", "requirements.txt"],
                },
                {
                    "type": "config_change",
                    "severity": "high",
                    "description": "Database schema changes requiring migration",
                    "files_affected": [
                        "internal/database/postgres.go",
                        "k8s/deployment.yaml",
                    ],
                },
            ],
        }

    @staticmethod
    def get_intelligence_response() -> dict[str, Any]:
        """Get complete intelligence API response with realistic data."""
        base_time = datetime.now(UTC)
        correlations = IntelligenceFixtures.get_realistic_correlations()

        return {
            "success": True,
            "total_documents": 4,
            "documents": [
                {
                    "id": "doc-1",
                    "created_at": (base_time - timedelta(hours=2)).isoformat(),
                    "repository": "omniagent",
                    "commit_sha": "abc123def456",
                    "author": "developer",
                    "change_type": "enhanced_code_changes_with_correlation",
                    "intelligence_data": {
                        "diff_analysis": {
                            "total_changes": 5,
                            "added_lines": 120,
                            "removed_lines": 30,
                            "modified_files": [
                                "src/api/endpoints.py",
                                "src/models/user.py",
                                "tests/test_api.py",
                                "requirements.txt",
                                "README.md",
                            ],
                        },
                        "correlation_analysis": correlations,
                    },
                }
            ],
        }


class ASCIIDashboard:
    """ASCII visualization tools for intelligence data."""

    @staticmethod
    def render_correlation_summary(data: dict[str, Any]) -> str:
        """Render correlation data as ASCII dashboard."""
        lines = []
        lines.append("=" * 80)
        lines.append("🧠 ARCHON INTELLIGENCE CORRELATION DASHBOARD")
        lines.append("=" * 80)
        lines.append("")

        # Summary stats
        temporal = data.get("temporal_correlations", [])
        semantic = data.get("semantic_correlations", [])
        breaking = data.get("breaking_changes", [])

        lines.append("📊 SUMMARY")
        lines.append(f"   Temporal Correlations: {len(temporal)}")
        lines.append(f"   Semantic Correlations: {len(semantic)}")
        lines.append(f"   Breaking Changes: {len(breaking)}")
        lines.append("")

        # Semantic correlations with file info
        if semantic:
            lines.append("🔗 SEMANTIC CORRELATIONS")
            lines.append("─" * 50)

            for i, corr in enumerate(semantic, 1):
                repo = corr.get("repository", "unknown")
                similarity = corr.get("semantic_similarity", 0.0)
                keywords = corr.get("common_keywords", [])
                file_info = corr.get("file_information", {})

                lines.append(
                    f"{i}. {repo} ({', '.join(keywords[:3])}) {similarity*100:.0f}%"
                )

                if file_info:
                    tech_stack = file_info.get("technology_stack", [])
                    extensions = file_info.get("common_extensions", [])
                    overlap = file_info.get("file_overlap_ratio", 0.0)

                    if tech_stack and tech_stack != ["Unknown"]:
                        lines.append(f"   🔧 Tech: {', '.join(tech_stack[:3])}")

                    if extensions and extensions != ["mixed"]:
                        ext_display = ", ".join(f".{ext}" for ext in extensions[:4])
                        lines.append(f"   📁 Files: {ext_display}")

                    if overlap > 0:
                        lines.append(f"   📈 Overlap: {overlap*100:.0f}%")

                lines.append("")

        # Temporal correlations
        if temporal:
            lines.append("⏱️  TEMPORAL CORRELATIONS")
            lines.append("─" * 50)

            for i, corr in enumerate(temporal, 1):
                repo = corr.get("repository", "unknown")
                strength = corr.get("correlation_strength", 0.0)
                time_diff = corr.get("time_diff_hours", 0.0)

                lines.append(
                    f"{i}. {repo} - {strength*100:.0f}% ({time_diff:.1f}h ago)"
                )

            lines.append("")

        # Breaking changes
        if breaking:
            lines.append("💥 BREAKING CHANGES")
            lines.append("─" * 50)

            for i, change in enumerate(breaking, 1):
                change_type = change.get("type", "unknown")
                severity = change.get("severity", "unknown")
                desc = change.get("description", "No description")

                lines.append(f"{i}. [{severity.upper()}] {change_type}")
                lines.append(f"   {desc}")

            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    @staticmethod
    def render_file_analysis(file_info: dict[str, Any]) -> str:
        """Render detailed file analysis."""
        lines = []
        lines.append("📁 FILE ANALYSIS BREAKDOWN")
        lines.append("─" * 40)

        tech_stack = file_info.get("technology_stack", [])
        if tech_stack:
            lines.append(f"🔧 Technology Stack: {', '.join(tech_stack)}")

        extensions = file_info.get("common_extensions", [])
        if extensions:
            lines.append(f"📄 File Extensions: {', '.join(extensions)}")

        directories = file_info.get("common_directories", [])
        if directories:
            lines.append(f"📂 Directories: {', '.join(directories)}")

        common_files = file_info.get("common_files", [])
        if common_files:
            lines.append(f"🔗 Common Files: {', '.join(common_files)}")

        overlap = file_info.get("file_overlap_ratio", 0.0)
        lines.append(f"📊 File Overlap: {overlap*100:.1f}%")

        return "\n".join(lines)

    @staticmethod
    def test_dashboard_display():
        """Test method to display sample dashboard."""
        print("🧪 Testing Intelligence Dashboard Fixtures\n")

        # Test correlation data
        correlations = IntelligenceFixtures.get_realistic_correlations()
        dashboard = ASCIIDashboard.render_correlation_summary(correlations)
        print(dashboard)

        # Test file analysis
        sample_file_info = correlations["semantic_correlations"][0]["file_information"]
        file_analysis = ASCIIDashboard.render_file_analysis(sample_file_info)
        print("\n" + file_analysis)


class IntelligenceDebugUtils:
    """Debug utilities for intelligence system."""

    @staticmethod
    def validate_file_information(file_info: dict[str, Any]) -> list[str]:
        """Validate file information structure and return issues."""
        issues = []

        required_fields = [
            "common_files",
            "common_extensions",
            "common_directories",
            "file_overlap_ratio",
            "technology_stack",
        ]

        for field in required_fields:
            if field not in file_info:
                issues.append(f"Missing required field: {field}")

        # Type validation
        array_fields = [
            "common_files",
            "common_extensions",
            "common_directories",
            "technology_stack",
        ]
        for field in array_fields:
            if field in file_info and not isinstance(file_info[field], list):
                issues.append(
                    f"Field {field} should be array, got {type(file_info[field])}"
                )

        # Value validation
        if "file_overlap_ratio" in file_info:
            ratio = file_info["file_overlap_ratio"]
            if not isinstance(ratio, int | float) or not (0.0 <= ratio <= 1.0):
                issues.append(f"file_overlap_ratio should be 0.0-1.0, got {ratio}")

        # Quality validation
        tech_stack = file_info.get("technology_stack", [])
        if tech_stack == ["Unknown"]:
            issues.append(
                "Technology stack is generic 'Unknown' - may indicate poor file analysis"
            )

        extensions = file_info.get("common_extensions", [])
        if extensions == ["mixed"]:
            issues.append(
                "Extensions are generic 'mixed' - may indicate poor file analysis"
            )

        return issues

    @staticmethod
    def compare_expected_vs_actual(
        expected: dict[str, Any], actual: dict[str, Any]
    ) -> str:
        """Compare expected vs actual correlation data and highlight differences."""
        lines = []
        lines.append("🔍 EXPECTED vs ACTUAL COMPARISON")
        lines.append("=" * 60)

        # Compare semantic correlations
        exp_semantic = expected.get("semantic_correlations", [])
        act_semantic = actual.get("semantic_correlations", [])

        lines.append(
            f"Semantic Correlations: Expected {len(exp_semantic)}, Got {len(act_semantic)}"
        )

        for i, (exp, act) in enumerate(zip(exp_semantic, act_semantic, strict=False)):
            lines.append(f"\nCorrelation {i+1}:")
            lines.append(
                f"  Repository: {exp.get('repository')} vs {act.get('repository')}"
            )

            exp_similarity = exp.get("semantic_similarity", 0)
            act_similarity = act.get("semantic_similarity", 0)
            lines.append(f"  Similarity: {exp_similarity:.2f} vs {act_similarity:.2f}")

            # Compare file information
            exp_file_info = exp.get("file_information", {})
            act_file_info = act.get("file_information", {})

            if exp_file_info and act_file_info:
                exp_tech = exp_file_info.get("technology_stack", [])
                act_tech = act_file_info.get("technology_stack", [])
                lines.append(f"  Tech Stack: {exp_tech} vs {act_tech}")

                exp_ext = exp_file_info.get("common_extensions", [])
                act_ext = act_file_info.get("common_extensions", [])
                lines.append(f"  Extensions: {exp_ext} vs {act_ext}")
            elif exp_file_info and not act_file_info:
                lines.append("  ❌ file_information missing in actual data")
            elif not exp_file_info and act_file_info:
                lines.append("  ⚠️  Unexpected file_information in actual data")

        return "\n".join(lines)


if __name__ == "__main__":
    # Run test display
    ASCIIDashboard.test_dashboard_display()
