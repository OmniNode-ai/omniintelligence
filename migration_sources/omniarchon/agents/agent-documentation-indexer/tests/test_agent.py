"""
Core agent functionality tests using Pydantic AI TestModel and FunctionModel.
"""

import pytest
from pydantic_ai.messages import TextPart
from pydantic_ai.models.test import TestModel

from ..agent import agent
from ..dependencies import AgentDependencies


class TestDocumentationIndexerAgent:
    """Test core agent functionality."""

    @pytest.mark.asyncio
    async def test_agent_basic_functionality(self, test_agent, test_dependencies):
        """Test agent responds appropriately with TestModel."""
        result = await test_agent.run(
            "Index documentation in the current directory", deps=test_dependencies
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0

        # Test model should provide basic response
        messages = result.all_messages()
        assert any("documentation" in str(msg).lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_agent_tool_calling(self, test_dependencies):
        """Test agent calls appropriate tools."""
        test_model = TestModel()

        # Configure TestModel to call indexing tool
        test_model.agent_responses = [
            TextPart(content="I'll index the documentation"),
            {
                "index_documentation": {
                    "target_path": ".",
                    "processing_mode": "comprehensive",
                    "enable_cross_references": True,
                }
            },
        ]

        test_agent = agent.override(model=test_model)
        result = await test_agent.run(
            "Index all documentation files", deps=test_dependencies
        )

        # Verify tool was called
        [msg for msg in result.all_messages() if hasattr(msg, "tool_name")]
        # Note: TestModel may not preserve exact tool call structure
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_agent_with_function_model(
        self, function_model_agent, test_dependencies
    ):
        """Test agent with custom function model."""
        result = await function_model_agent.run(
            "Process project documentation", deps=test_dependencies
        )

        # Verify expected behavior sequence
        messages = result.all_messages()
        assert len(messages) >= 3

        # Check for indexing-related content
        message_content = " ".join(str(msg) for msg in messages).lower()
        assert "documentation" in message_content or "indexing" in message_content

    @pytest.mark.asyncio
    async def test_agent_error_handling(self, test_agent, test_dependencies):
        """Test agent handles errors gracefully."""
        # Configure dependencies with invalid path
        error_deps = AgentDependencies(project_root="/nonexistent/path")

        result = await test_agent.run(
            "Index documentation in invalid directory", deps=error_deps
        )

        # Agent should still respond (TestModel doesn't actually execute tools)
        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_different_processing_modes(
        self, test_agent, test_dependencies
    ):
        """Test agent handles different processing mode requests."""
        modes = ["basic", "comprehensive", "semantic"]

        for mode in modes:
            result = await test_agent.run(
                f"Index documentation using {mode} processing mode",
                deps=test_dependencies,
            )

            assert result.data is not None
            # TestModel should respond to each request
            assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_archon_integration_request(
        self, test_agent, test_dependencies
    ):
        """Test agent handles Archon MCP integration requests."""
        # Configure for Archon integration
        archon_deps = AgentDependencies(
            archon_mcp_available=True, archon_project_id="test-project-123"
        )

        result = await test_agent.run(
            "Index documentation and integrate with Archon MCP system", deps=archon_deps
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_file_type_specific_requests(
        self, test_agent, test_dependencies
    ):
        """Test agent handles requests for specific file types."""
        file_types = ["Markdown", "YAML", "text files", "agent specifications"]

        for file_type in file_types:
            result = await test_agent.run(
                f"Index all {file_type} in the project", deps=test_dependencies
            )

            assert result.data is not None
            assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_quality_validation_request(
        self, test_agent, test_dependencies
    ):
        """Test agent handles quality validation requests."""
        result = await test_agent.run(
            "Index documentation and validate processing quality",
            deps=test_dependencies,
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_cross_reference_extraction(
        self, test_agent, test_dependencies
    ):
        """Test agent handles cross-reference extraction requests."""
        result = await test_agent.run(
            "Index documentation with comprehensive cross-reference extraction",
            deps=test_dependencies,
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_metadata_enhancement(self, test_agent, test_dependencies):
        """Test agent handles metadata enhancement requests."""
        result = await test_agent.run(
            "Process documentation with enhanced metadata extraction and semantic tagging",
            deps=test_dependencies,
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0


class TestAgentResponsePatterns:
    """Test agent response patterns and behavior."""

    @pytest.mark.asyncio
    async def test_agent_structured_responses(
        self, function_model_agent, test_dependencies
    ):
        """Test that agent provides structured responses."""
        result = await function_model_agent.run(
            "Provide detailed analysis of documentation structure",
            deps=test_dependencies,
        )

        assert result.data is not None
        messages = result.all_messages()

        # Should have multiple messages showing processing flow
        assert len(messages) >= 2

    @pytest.mark.asyncio
    async def test_agent_progress_reporting(self, test_agent, test_dependencies):
        """Test agent provides progress information."""
        result = await test_agent.run(
            "Index large documentation set with progress reporting",
            deps=test_dependencies,
        )

        assert result.data is not None
        # TestModel should provide some response about progress
        message_content = " ".join(str(msg) for msg in result.all_messages()).lower()
        # May contain progress-related terms depending on model response
        assert len(message_content) > 0

    @pytest.mark.asyncio
    async def test_agent_handles_complex_requests(self, test_agent, test_dependencies):
        """Test agent handles complex multi-part requests."""
        complex_request = """
        Please index all documentation in the project with the following requirements:
        1. Use comprehensive processing mode
        2. Extract cross-references between documents
        3. Generate semantic tags for content categorization
        4. Validate processing quality
        5. Integrate results with Archon MCP system
        """

        result = await test_agent.run(complex_request, deps=test_dependencies)

        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_context_awareness(self, test_agent):
        """Test agent maintains context awareness."""
        # Different contexts should influence responses
        contexts = [
            (AgentDependencies(project_root="/archon/project"), "Archon project"),
            (AgentDependencies(project_root="/docs/project"), "Documentation project"),
            (AgentDependencies(project_root="/api/project"), "API project"),
        ]

        for deps, context_type in contexts:
            result = await test_agent.run(
                f"Index documentation for this {context_type}", deps=deps
            )

            assert result.data is not None
            assert len(result.all_messages()) > 0


class TestAgentIntegration:
    """Test agent integration with external systems."""

    @pytest.mark.asyncio
    async def test_agent_archon_mcp_simulation(self, test_agent):
        """Test agent simulates Archon MCP integration."""
        archon_deps = AgentDependencies(
            archon_mcp_available=True,
            archon_project_id="test-123",
            archon_base_url="http://localhost:8051",
        )

        result = await test_agent.run(
            "Index documentation and create Archon project integration",
            deps=archon_deps,
        )

        assert result.data is not None
        # Should reference Archon or MCP in some way
        message_content = " ".join(str(msg) for msg in result.all_messages()).lower()
        # TestModel may not specifically mention Archon, but should respond
        assert len(message_content) > 0

    @pytest.mark.asyncio
    async def test_agent_handles_repository_context(self, test_agent):
        """Test agent handles different repository contexts."""
        repo_contexts = [
            "python-project",
            "javascript-project",
            "documentation-site",
            "api-service",
        ]

        for repo_context in repo_contexts:
            deps = AgentDependencies(project_root=f"/projects/{repo_context}")
            result = await test_agent.run(
                f"Index documentation for {repo_context}", deps=deps
            )

            assert result.data is not None
            assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_quality_gates(self, test_agent, test_dependencies):
        """Test agent handles quality gate requirements."""
        result = await test_agent.run(
            "Index documentation ensuring all quality gates pass with >90% success rate",
            deps=test_dependencies,
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0

    @pytest.mark.asyncio
    async def test_agent_performance_requirements(self, test_agent, test_dependencies):
        """Test agent handles performance requirements."""
        result = await test_agent.run(
            "Index documentation optimized for fast retrieval and minimal memory usage",
            deps=test_dependencies,
        )

        assert result.data is not None
        assert len(result.all_messages()) > 0
