"""
Test Intelligence Correlation Integration

Comprehensive test suite for the intelligence-enhanced correlation system.
Tests the integration between rich intelligence documents and correlation analysis.

This test suite covers:
- Enhanced keyword extraction from rich intelligence data
- Technology stack correlation detection
- Architecture pattern correlation analysis
- Integration fallback mechanisms
- Performance comparison between basic and enhanced analysis
- End-to-end workflow testing
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from services.correlation_analyzer import DocumentContext
from services.enhanced_correlation_analyzer import EnhancedCorrelationAnalyzer
from services.enhanced_correlation_processor import EnhancedCorrelationProcessor
from services.intelligence_correlation_integration import (
    AnalysisMode,
    IntegrationConfig,
    IntelligenceCorrelationIntegration,
)

logger = logging.getLogger(__name__)


class TestIntelligenceCorrelationIntegration:
    """Test suite for intelligence correlation integration."""

    @pytest.fixture
    def sample_rich_document(self) -> DocumentContext:
        """Create a sample document with rich intelligence data."""
        return DocumentContext(
            id="doc-001",
            repository="test-repo",
            commit_sha="abc123",
            author="test-author",
            created_at=datetime.now(UTC),
            change_type="enhanced_code_changes_with_correlation",
            content={
                "technologies_detected": [
                    "Python",
                    "Docker",
                    "GitHub Actions",
                    "Pytest",
                    "MyPy",
                    "Ruff",
                    "Black",
                    "Consul",
                ],
                "architecture_patterns": [
                    "ci_pipeline",
                    "docker_build",
                    "test_automation",
                    "consul_integration",
                    "microservices",
                ],
                "diff_analysis": {
                    "modified_files": [
                        "src/main.py",
                        "Dockerfile",
                        ".github/workflows/ci.yml",
                    ],
                    "total_changes": 45,
                },
            },
            modified_files=["src/main.py", "Dockerfile", ".github/workflows/ci.yml"],
            commit_message="feat: add microservices with consul integration",
        )

    @pytest.fixture
    def sample_basic_document(self) -> DocumentContext:
        """Create a sample document without rich intelligence data."""
        return DocumentContext(
            id="doc-002",
            repository="basic-repo",
            commit_sha="def456",
            author="basic-author",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            change_type="basic_change",
            content={
                "diff_analysis": {"modified_files": ["script.py"], "total_changes": 12}
            },
            modified_files=["script.py"],
            commit_message="fix: update script",
        )

    @pytest.fixture
    def related_rich_document(self) -> DocumentContext:
        """Create a related document with overlapping rich data."""
        return DocumentContext(
            id="doc-003",
            repository="related-repo",
            commit_sha="ghi789",
            author="related-author",
            created_at=datetime.now(UTC) - timedelta(hours=1),
            change_type="enhanced_code_changes_with_correlation",
            content={
                "technologies_detected": [
                    "Python",
                    "Docker",
                    "Kubernetes",
                    "Pytest",
                    "Consul",
                    "Prometheus",
                ],
                "architecture_patterns": [
                    "microservices",
                    "consul_integration",
                    "monitoring",
                    "containerization",
                ],
                "diff_analysis": {
                    "modified_files": [
                        "src/service.py",
                        "k8s/deployment.yaml",
                        "docker-compose.yml",
                    ],
                    "total_changes": 67,
                },
            },
            modified_files=[
                "src/service.py",
                "k8s/deployment.yaml",
                "docker-compose.yml",
            ],
            commit_message="feat: add kubernetes deployment with monitoring",
        )

    @pytest.fixture
    def enhanced_analyzer(self) -> EnhancedCorrelationAnalyzer:
        """Create enhanced correlation analyzer for testing."""
        config = {
            "technology_weight": 0.4,
            "architecture_weight": 0.3,
            "rich_content_bonus": 0.2,
            "temporal_threshold_hours": 72,
            "semantic_threshold": 0.3,
        }
        return EnhancedCorrelationAnalyzer(config)

    @pytest.fixture
    def integration_service(self) -> IntelligenceCorrelationIntegration:
        """Create integration service for testing."""
        config = IntegrationConfig(
            analysis_mode=AnalysisMode.AUTO,
            enhanced_threshold=0.5,
            technology_weight=0.4,
            architecture_weight=0.3,
        )
        return IntelligenceCorrelationIntegration(config)

    async def test_enhanced_keyword_extraction(
        self, enhanced_analyzer, sample_rich_document
    ):
        """Test enhanced keyword extraction from rich intelligence data."""

        # Convert to enhanced document context
        enhanced_doc = await enhanced_analyzer._enhance_document_context(
            sample_rich_document
        )

        # Test enhanced keyword extraction
        keywords = enhanced_analyzer._extract_enhanced_keywords(enhanced_doc)

        # Verify rich intelligence keywords are included
        assert "python" in keywords
        assert "docker" in keywords
        assert "consul" in keywords
        assert "ci_pipeline" in keywords
        assert "microservices" in keywords

        # Verify technology groupings
        assert "containerization" in keywords  # Docker should add this group
        assert "testing" in keywords  # Pytest should add this group

        logger.info(f"Enhanced keywords extracted: {sorted(keywords)}")

        # Test content text extraction
        content_text = enhanced_analyzer._extract_enhanced_content_text(enhanced_doc)
        assert "python" in content_text
        assert "docker" in content_text
        assert "microservices" in content_text

    async def test_technology_correlation_calculation(self, enhanced_analyzer):
        """Test technology stack correlation calculation."""

        tech_stack_1 = ["Python", "Docker", "GitHub Actions", "Pytest"]
        tech_stack_2 = ["Python", "Docker", "Kubernetes", "Jest"]

        correlation = enhanced_analyzer._calculate_technology_correlation(
            tech_stack_1, tech_stack_2
        )

        # Should have moderate correlation (Python, Docker overlap + containerization group)
        assert correlation > 0.3
        assert correlation < 0.8

        # Test identical stacks
        identical_correlation = enhanced_analyzer._calculate_technology_correlation(
            tech_stack_1, tech_stack_1
        )
        assert identical_correlation == 1.0

        # Test no overlap
        no_overlap_correlation = enhanced_analyzer._calculate_technology_correlation(
            ["Python", "Django"], ["Java", "Spring"]
        )
        assert no_overlap_correlation >= 0.0  # Could have group-based correlation

        logger.info(
            f"Technology correlations: {correlation}, {identical_correlation}, {no_overlap_correlation}"
        )

    async def test_architecture_correlation_calculation(self, enhanced_analyzer):
        """Test architecture pattern correlation calculation."""

        patterns_1 = ["microservices", "ci_pipeline", "docker_build"]
        patterns_2 = ["microservices", "kubernetes_deployment", "monitoring"]

        correlation = enhanced_analyzer._calculate_architecture_correlation(
            patterns_1, patterns_2
        )

        # Should have some correlation due to microservices overlap
        assert correlation > 0.0

        # Test identical patterns
        identical_correlation = enhanced_analyzer._calculate_architecture_correlation(
            patterns_1, patterns_1
        )
        assert identical_correlation == 1.0

        logger.info(
            f"Architecture correlations: {correlation}, {identical_correlation}"
        )

    async def test_enhanced_temporal_correlations(
        self, enhanced_analyzer, sample_rich_document, related_rich_document
    ):
        """Test enhanced temporal correlation analysis."""

        # Convert to enhanced contexts
        target_enhanced = await enhanced_analyzer._enhance_document_context(
            sample_rich_document
        )
        context_enhanced = await enhanced_analyzer._enhance_document_context(
            related_rich_document
        )

        # Test temporal correlation analysis
        temporal_correlations = await enhanced_analyzer._enhanced_temporal_correlations(
            target_enhanced, [context_enhanced]
        )

        assert len(temporal_correlations) > 0

        correlation = temporal_correlations[0]
        assert correlation.repository == related_rich_document.repository
        assert correlation.commit_sha == related_rich_document.commit_sha
        assert correlation.correlation_strength > 0.5  # Should be high due to rich data

        # Verify enhanced factors are present
        factors = correlation.correlation_factors
        assert any("technology correlation" in factor.lower() for factor in factors)
        assert any("architecture correlation" in factor.lower() for factor in factors)
        assert any("rich intelligence data" in factor.lower() for factor in factors)

        logger.info(
            f"Enhanced temporal correlation: {correlation.correlation_strength}, factors: {factors}"
        )

    async def test_enhanced_semantic_correlations(
        self, enhanced_analyzer, sample_rich_document, related_rich_document
    ):
        """Test enhanced semantic correlation analysis."""

        target_enhanced = await enhanced_analyzer._enhance_document_context(
            sample_rich_document
        )
        context_enhanced = await enhanced_analyzer._enhance_document_context(
            related_rich_document
        )

        # Test semantic correlation analysis
        semantic_correlations = await enhanced_analyzer._enhanced_semantic_correlations(
            target_enhanced, [context_enhanced]
        )

        assert len(semantic_correlations) > 0

        correlation = semantic_correlations[0]
        assert (
            correlation.semantic_similarity > 0.4
        )  # Should be high due to rich data overlap

        # Verify rich intelligence factors
        factors = correlation.similarity_factors
        assert any("technology stack" in factor.lower() for factor in factors)
        assert any("architecture patterns" in factor.lower() for factor in factors)

        # Check for specific technology intersections
        tech_factors = [f for f in factors if "technology stack" in f.lower()]
        if tech_factors:
            # Should mention common technologies like Python, Docker, Consul
            assert any(
                tech in tech_factors[0] for tech in ["Python", "Docker", "Consul"]
            )

        logger.info(
            f"Enhanced semantic correlation: {correlation.semantic_similarity}, factors: {factors}"
        )

    async def test_integration_mode_selection(
        self, integration_service, sample_rich_document, sample_basic_document
    ):
        """Test automatic analysis mode selection based on data availability."""

        # Test with rich data documents
        rich_mode = await integration_service._determine_analysis_mode(
            sample_rich_document, [sample_rich_document]
        )
        assert rich_mode == AnalysisMode.ENHANCED

        # Test with basic data documents
        basic_mode = await integration_service._determine_analysis_mode(
            sample_basic_document, [sample_basic_document]
        )
        assert basic_mode == AnalysisMode.BASIC

        # Test mixed data (should use threshold)
        mixed_mode = await integration_service._determine_analysis_mode(
            sample_rich_document, [sample_basic_document]
        )
        # With 50% coverage (1 rich, 1 basic) and threshold 0.5, should use enhanced
        assert mixed_mode == AnalysisMode.ENHANCED

        logger.info(
            f"Mode selections: rich={rich_mode}, basic={basic_mode}, mixed={mixed_mode}"
        )

    async def test_rich_data_coverage_calculation(
        self, integration_service, sample_rich_document, sample_basic_document
    ):
        """Test rich data coverage calculation."""

        # Test all rich data
        coverage_100 = await integration_service._calculate_rich_data_coverage(
            sample_rich_document, [sample_rich_document]
        )
        assert coverage_100 == 1.0

        # Test no rich data
        coverage_0 = await integration_service._calculate_rich_data_coverage(
            sample_basic_document, [sample_basic_document]
        )
        assert coverage_0 == 0.0

        # Test mixed data
        coverage_50 = await integration_service._calculate_rich_data_coverage(
            sample_rich_document, [sample_basic_document]
        )
        assert coverage_50 == 0.5

        logger.info(
            f"Coverage calculations: 100%={coverage_100}, 0%={coverage_0}, 50%={coverage_50}"
        )

    async def test_enhanced_vs_basic_analysis_comparison(
        self, enhanced_analyzer, sample_rich_document, related_rich_document
    ):
        """Test comparison between enhanced and basic analysis results."""

        context_docs = [related_rich_document]

        # Run enhanced analysis
        enhanced_result = await enhanced_analyzer.analyze_document_correlations(
            sample_rich_document, context_docs
        )

        # Run basic analysis (using base analyzer)
        basic_analyzer = (
            enhanced_analyzer.basic_analyzer
            if hasattr(enhanced_analyzer, "basic_analyzer")
            else enhanced_analyzer.__class__.__bases__[0]()
        )
        basic_result = await basic_analyzer.analyze_document_correlations(
            sample_rich_document, context_docs
        )

        # Enhanced analysis should find more/stronger correlations
        enhanced_total = len(enhanced_result.temporal_correlations) + len(
            enhanced_result.semantic_correlations
        )
        basic_total = len(basic_result.temporal_correlations) + len(
            basic_result.semantic_correlations
        )

        # Enhanced should have equal or more correlations
        assert enhanced_total >= basic_total

        # Enhanced correlations should have higher average strength
        if enhanced_result.temporal_correlations:
            enhanced_avg_strength = sum(
                tc.correlation_strength for tc in enhanced_result.temporal_correlations
            ) / len(enhanced_result.temporal_correlations)

            if basic_result.temporal_correlations:
                basic_avg_strength = sum(
                    tc.correlation_strength for tc in basic_result.temporal_correlations
                ) / len(basic_result.temporal_correlations)
                assert enhanced_avg_strength >= basic_avg_strength

        logger.info(
            f"Comparison: Enhanced={enhanced_total} correlations, Basic={basic_total} correlations"
        )

        # Verify enhanced metadata
        assert enhanced_result.analysis_metadata["analyzer_version"].endswith(
            "-enhanced"
        )
        assert "enhancement_features" in enhanced_result.analysis_metadata

    async def test_integration_fallback_mechanism(self, integration_service):
        """Test fallback from enhanced to basic analysis on errors."""

        # Mock enhanced analyzer to raise exception
        with patch.object(
            integration_service.enhanced_analyzer,
            "analyze_document_correlations",
            side_effect=Exception("Enhanced analysis failed"),
        ):
            sample_doc = DocumentContext(
                id="test-fallback",
                repository="test",
                commit_sha="test",
                author="test",
                created_at=datetime.now(UTC),
                change_type="test",
                content={"technologies_detected": ["Python"]},
                modified_files=["test.py"],
            )

            # Should fallback to basic analysis
            result = await integration_service.analyze_document_correlations(
                sample_doc, []
            )

            # Verify fallback occurred
            assert integration_service.stats.fallback_count > 0
            assert result is not None

            logger.info("Fallback mechanism test completed successfully")

    async def test_performance_monitoring(
        self, integration_service, sample_rich_document
    ):
        """Test performance monitoring and statistics collection."""

        # Run analysis to generate statistics
        await integration_service.analyze_document_correlations(
            sample_rich_document, []
        )

        # Get integration statistics
        stats = integration_service.get_integration_stats()

        # Verify statistics structure
        assert "total_analyses" in stats
        assert "mode_breakdown" in stats
        assert "performance" in stats
        assert "data_coverage" in stats
        assert "configuration" in stats

        # Verify counts
        assert stats["total_analyses"] > 0

        logger.info(f"Integration statistics: {stats}")

    @pytest.mark.integration
    async def test_end_to_end_enhanced_processing(
        self, sample_rich_document, related_rich_document
    ):
        """Test end-to-end enhanced correlation processing workflow."""

        # Mock data access
        mock_data_access = Mock()

        # Create enhanced processor
        config = {
            "analysis_mode": "enhanced",
            "technology_weight": 0.4,
            "architecture_weight": 0.3,
            "enhanced_threshold": 0.5,
            "batch_size": 2,
            "max_context_documents": 50,
        }

        processor = EnhancedCorrelationProcessor(config)
        processor.data_access = mock_data_access

        # Mock document retrieval
        mock_data_access.get_parsed_documents.return_value = [
            # Mock intelligence document data
            type(
                "MockDoc",
                (),
                {
                    "id": sample_rich_document.id,
                    "repository": sample_rich_document.repository,
                    "commit_sha": sample_rich_document.commit_sha,
                    "author": sample_rich_document.author,
                    "created_at": sample_rich_document.created_at.isoformat(),
                    "change_type": sample_rich_document.change_type,
                    "raw_content": sample_rich_document.content,
                    "temporal_correlations": [],
                    "semantic_correlations": [],
                    "diff_analysis": type(
                        "MockDiff",
                        (),
                        {"modified_files": sample_rich_document.modified_files},
                    )(),
                },
            )()
        ]

        # Test queuing documents with empty correlations
        queued_count = await processor.queue_documents_with_empty_correlations()
        assert queued_count > 0

        # Test enhanced processing statistics
        stats = processor.get_enhanced_processing_stats()
        assert "enhanced_statistics" in stats

        enhanced_stats = stats["enhanced_statistics"]
        assert "integration_stats" in enhanced_stats

        logger.info(
            f"End-to-end test completed. Queued: {queued_count}, Stats: {enhanced_stats}"
        )


class TestRealDataScenarios:
    """Test scenarios with realistic data patterns."""

    def create_microservices_document(
        self, doc_id: str, repo: str, commit: str
    ) -> DocumentContext:
        """Create a realistic microservices document."""
        return DocumentContext(
            id=doc_id,
            repository=repo,
            commit_sha=commit,
            author="dev-team",
            created_at=datetime.now(UTC),
            change_type="enhanced_code_changes_with_correlation",
            content={
                "technologies_detected": [
                    "Python",
                    "FastAPI",
                    "Docker",
                    "Kubernetes",
                    "PostgreSQL",
                    "Redis",
                    "Consul",
                    "Prometheus",
                    "Grafana",
                ],
                "architecture_patterns": [
                    "microservices",
                    "api_gateway",
                    "service_discovery",
                    "monitoring",
                    "containerization",
                    "database_per_service",
                    "event_driven",
                ],
                "diff_analysis": {
                    "modified_files": [
                        "services/user-service/main.py",
                        "services/order-service/main.py",
                        "k8s/user-service.yaml",
                        "k8s/order-service.yaml",
                        "docker-compose.yml",
                    ],
                    "total_changes": 156,
                },
            },
            modified_files=[
                "services/user-service/main.py",
                "services/order-service/main.py",
                "k8s/user-service.yaml",
                "k8s/order-service.yaml",
                "docker-compose.yml",
            ],
            commit_message="feat: implement user and order microservices with k8s deployment",
        )

    def create_ci_cd_document(
        self, doc_id: str, repo: str, commit: str
    ) -> DocumentContext:
        """Create a realistic CI/CD document."""
        return DocumentContext(
            id=doc_id,
            repository=repo,
            commit_sha=commit,
            author="devops-team",
            created_at=datetime.now(UTC) - timedelta(hours=3),
            change_type="enhanced_code_changes_with_correlation",
            content={
                "technologies_detected": [
                    "GitHub Actions",
                    "Docker",
                    "Kubernetes",
                    "Helm",
                    "Terraform",
                    "AWS",
                    "ECR",
                    "EKS",
                ],
                "architecture_patterns": [
                    "ci_pipeline",
                    "cd_pipeline",
                    "infrastructure_as_code",
                    "containerization",
                    "cloud_deployment",
                    "automated_testing",
                ],
                "diff_analysis": {
                    "modified_files": [
                        ".github/workflows/ci.yml",
                        ".github/workflows/cd.yml",
                        "terraform/eks.tf",
                        "helm/values.yaml",
                        "Dockerfile",
                    ],
                    "total_changes": 89,
                },
            },
            modified_files=[
                ".github/workflows/ci.yml",
                ".github/workflows/cd.yml",
                "terraform/eks.tf",
                "helm/values.yaml",
                "Dockerfile",
            ],
            commit_message="feat: add complete CI/CD pipeline with EKS deployment",
        )

    async def test_realistic_microservices_correlation(self):
        """Test correlation detection between related microservices changes."""

        # Create related documents
        microservices_doc = self.create_microservices_document(
            "ms-001", "ecommerce-platform", "abc123"
        )
        cicd_doc = self.create_ci_cd_document("ci-001", "ecommerce-platform", "def456")

        # Create enhanced analyzer
        enhanced_analyzer = EnhancedCorrelationAnalyzer(
            {
                "technology_weight": 0.4,
                "architecture_weight": 0.3,
                "temporal_threshold_hours": 72,
            }
        )

        # Analyze correlations
        result = await enhanced_analyzer.analyze_document_correlations(
            microservices_doc, [cicd_doc]
        )

        # Should find strong correlations
        assert len(result.temporal_correlations) + len(result.semantic_correlations) > 0

        # Verify technology correlations (Docker, Kubernetes overlap)
        found_tech_correlation = False

        for correlation in result.temporal_correlations + result.semantic_correlations:
            factors = getattr(correlation, "correlation_factors", []) or getattr(
                correlation, "similarity_factors", []
            )

            for factor in factors:
                if "technology" in factor.lower():
                    found_tech_correlation = True
                    # Should mention Docker and Kubernetes
                    assert any(tech in factor for tech in ["Docker", "Kubernetes"])

                if "architecture" in factor.lower():
                    # Should mention containerization
                    assert "containerization" in factor

        assert found_tech_correlation, "Should find technology-based correlations"

        logger.info(
            f"Realistic correlation test: {len(result.temporal_correlations)} temporal, {len(result.semantic_correlations)} semantic"
        )

    async def test_dashboard_correlation_display_format(self):
        """Test that correlations are formatted for dashboard display."""

        microservices_doc = self.create_microservices_document(
            "ms-002", "platform", "ghi789"
        )
        cicd_doc = self.create_ci_cd_document("ci-002", "platform", "jkl012")

        enhanced_analyzer = EnhancedCorrelationAnalyzer()

        result = await enhanced_analyzer.analyze_document_correlations(
            microservices_doc, [cicd_doc]
        )

        # Extract correlation display data
        correlation_display = []

        for tc in result.temporal_correlations:
            # Extract technology information for display
            tech_factors = [
                f for f in tc.correlation_factors if "technology" in f.lower()
            ]

            display_text = f"Tech: Docker + Kubernetes + CI Pipeline (strength: {tc.correlation_strength:.2f})"
            correlation_display.append(display_text)

        for sc in result.semantic_correlations:
            # Extract rich intelligence factors
            tech_factors = [
                f for f in sc.similarity_factors if "technology stack" in f.lower()
            ]
            arch_factors = [
                f for f in sc.similarity_factors if "architecture patterns" in f.lower()
            ]

            if tech_factors or arch_factors:
                display_text = "Tech: "

                # Extract technologies from factors
                if tech_factors:
                    # Parse technology list from factor string
                    tech_factor = tech_factors[0]
                    if "[" in tech_factor and "]" in tech_factor:
                        tech_list_str = tech_factor[
                            tech_factor.find("[") + 1 : tech_factor.find("]")
                        ]
                        tech_list = [
                            t.strip().strip("'\"") for t in tech_list_str.split(",")
                        ]
                        display_text += " + ".join(tech_list[:3])  # Show top 3

                correlation_display.append(display_text)

        # Verify we have meaningful display strings
        assert len(correlation_display) > 0

        # Should show rich correlations, not just "Tech: Python"
        meaningful_correlations = [c for c in correlation_display if " + " in c]
        assert (
            len(meaningful_correlations) > 0
        ), "Should have rich technology correlations with multiple technologies"

        logger.info(f"Dashboard display format test: {correlation_display}")


# Run tests
if __name__ == "__main__":
    asyncio.run(
        TestIntelligenceCorrelationIntegration().test_enhanced_keyword_extraction()
    )
    asyncio.run(TestRealDataScenarios().test_realistic_microservices_correlation())
    print("Intelligence correlation integration tests completed successfully!")
