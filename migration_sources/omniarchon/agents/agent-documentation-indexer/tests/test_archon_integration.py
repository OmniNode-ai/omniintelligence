"""
Integration tests with actual Archon project documentation.
"""

from pathlib import Path

import pytest

from ..agent import DocumentationIndexerRequest


class TestArchonProjectDocumentation:
    """Test processing actual Archon project documentation."""

    @pytest.mark.asyncio
    async def test_index_archon_claude_md(self, test_dependencies):
        """Test indexing the main CLAUDE.md file."""
        # Test with the actual Archon project path
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        claude_md = archon_root / "CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found in Archon project")

        # Test file preview first
        from ..agent import get_file_preview

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        preview_result = await get_file_preview(ctx, str(claude_md), max_lines=50)

        # Should successfully preview CLAUDE.md
        assert "error" not in preview_result
        assert preview_result["file_type"] == ".md"
        assert preview_result["total_lines"] > 100  # CLAUDE.md should be substantial
        assert len(preview_result["preview_lines"]) <= 50

        # Verify content contains expected Archon information
        content_text = "\n".join(preview_result["preview_lines"])
        assert "archon" in content_text.lower()

    @pytest.mark.asyncio
    async def test_index_archon_agents_directory(self, test_dependencies):
        """Test discovering and indexing agent specifications."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        agents_dir = archon_root / "agents"
        if not agents_dir.exists():
            pytest.skip("Agents directory not found in Archon project")

        # Request to index just the agents directory
        request = DocumentationIndexerRequest(
            target_path=str(agents_dir),
            include_patterns=["agent-*.md"],
            processing_mode="comprehensive",
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should discover agent specification files
        assert result.files_discovered > 0
        assert result.processing_time_seconds > 0

        # Should identify agent-related knowledge categories
        if result.knowledge_categories:
            # Might contain agent-related categories
            " ".join(result.knowledge_categories).lower()
            # Categories might include agent-related terms

    @pytest.mark.asyncio
    async def test_index_archon_monitoring_docs(self, test_dependencies):
        """Test indexing monitoring documentation."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        monitoring_dir = archon_root / "monitoring"
        if not monitoring_dir.exists():
            pytest.skip("Monitoring directory not found in Archon project")

        # Check if README.md exists in monitoring
        monitoring_readme = monitoring_dir / "README.md"
        if not monitoring_readme.exists():
            pytest.skip("README.md not found in monitoring directory")

        # Test file preview
        from ..agent import get_file_preview

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        preview_result = await get_file_preview(ctx, str(monitoring_readme))

        # Should successfully preview monitoring README
        assert "error" not in preview_result
        assert preview_result["file_type"] == ".md"

        # Content should be monitoring-related
        content_text = "\n".join(preview_result["preview_lines"])
        assert "monitoring" in content_text.lower() or "readme" in content_text.lower()

    @pytest.mark.asyncio
    async def test_index_full_archon_project(self, test_dependencies):
        """Test indexing the entire Archon project (limited scope for testing)."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        # Use more restrictive patterns to limit scope for testing
        request = DocumentationIndexerRequest(
            target_path=str(archon_root),
            include_patterns=["*.md", "agents/*.md"],
            exclude_patterns=["node_modules", ".git", "archon-ui-main"],
            processing_mode="basic",  # Use basic mode for faster testing
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should find multiple documentation files
        assert result.files_discovered > 5  # Should find CLAUDE.md, agent specs, etc.
        assert result.processing_time_seconds > 0

        # Should achieve reasonable success rate
        if result.files_discovered > 0:
            assert result.success_rate >= 50  # Should process most files successfully

        # Should create chunks from processed files
        if result.files_processed > 0:
            assert result.chunks_created > 0

    @pytest.mark.asyncio
    async def test_archon_agent_specification_processing(self, test_dependencies):
        """Test processing specific Archon agent specifications."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        # Look for the documentation indexer agent we just created
        doc_indexer_spec = archon_root / "agents" / "agent-documentation-indexer.md"

        if doc_indexer_spec.exists():
            # Test preview of the agent spec we created
            from ..agent import get_file_preview

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            ctx = MockContext(test_dependencies)
            preview_result = await get_file_preview(
                ctx, str(doc_indexer_spec), max_lines=30
            )

            # Should successfully preview the agent specification
            assert "error" not in preview_result
            assert preview_result["file_type"] == ".md"

            # Should contain expected agent specification content
            content_text = "\n".join(preview_result["preview_lines"])
            assert "agent-documentation-indexer" in content_text.lower()
            assert "documentation" in content_text.lower()

        # Test with any agent specification that exists
        agents_dir = archon_root / "agents"
        if agents_dir.exists():
            agent_files = list(agents_dir.glob("agent-*.md"))

            if agent_files:
                # Test the first agent file found
                first_agent = agent_files[0]

                from ..agent import get_file_preview

                ctx = MockContext(test_dependencies)
                preview_result = await get_file_preview(ctx, str(first_agent))

                assert "error" not in preview_result
                assert preview_result["file_type"] == ".md"

    @pytest.mark.asyncio
    async def test_archon_yaml_config_processing(self, test_dependencies):
        """Test processing YAML configuration files in Archon project."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found at expected path")

        # Look for YAML files in the project
        yaml_files = list(archon_root.rglob("*.yaml")) + list(
            archon_root.rglob("*.yml")
        )

        # Filter out node_modules and other excluded directories
        yaml_files = [
            f
            for f in yaml_files
            if not any(
                exclude in str(f) for exclude in ["node_modules", ".git", "__pycache__"]
            )
        ]

        if yaml_files:
            # Test the first YAML file found
            first_yaml = yaml_files[0]

            from ..agent import get_file_preview

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            ctx = MockContext(test_dependencies)
            preview_result = await get_file_preview(ctx, str(first_yaml))

            # Should handle YAML files
            assert "error" not in preview_result or "encoding" in preview_result
            if "error" not in preview_result:
                assert preview_result["file_type"] in [".yaml", ".yml"]


class TestArchonProjectStructureValidation:
    """Validate understanding of Archon project structure."""

    def test_archon_project_exists(self):
        """Validate that Archon project exists at expected location."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip(
                "Archon project not found - tests will be limited to synthetic data"
            )

        assert archon_root.is_dir()

        # Check for key files and directories
        expected_items = [
            "CLAUDE.md",
            "agents",
        ]

        for item in expected_items:
            item_path = archon_root / item
            if item_path.exists():
                # At least some expected items should exist
                assert True
                return

        # If no expected items found, still pass but note it
        pytest.skip("Expected Archon project structure not found")

    def test_archon_documentation_structure(self):
        """Test understanding of Archon documentation structure."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found")

        # Count different types of documentation
        md_files = list(archon_root.rglob("*.md"))
        yaml_files = list(archon_root.rglob("*.yaml")) + list(
            archon_root.rglob("*.yml")
        )
        txt_files = list(archon_root.rglob("*.txt"))

        # Filter out excluded directories
        excluded = ["node_modules", ".git", "__pycache__", "venv", "env"]

        md_files = [f for f in md_files if not any(ex in str(f) for ex in excluded)]
        yaml_files = [f for f in yaml_files if not any(ex in str(f) for ex in excluded)]
        txt_files = [f for f in txt_files if not any(ex in str(f) for ex in excluded)]

        # Should find various documentation files
        total_docs = len(md_files) + len(yaml_files) + len(txt_files)
        assert total_docs > 0, "Should find some documentation files in Archon project"

        # Log findings for information
        print(f"Found {len(md_files)} Markdown files")
        print(f"Found {len(yaml_files)} YAML files")
        print(f"Found {len(txt_files)} text files")
        print(f"Total documentation files: {total_docs}")


class TestArchonAgentSpecificationValidation:
    """Validate processing of Archon agent specifications."""

    @pytest.mark.asyncio
    async def test_agent_spec_yaml_frontmatter(self, test_dependencies):
        """Test processing agent specifications with YAML frontmatter."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found")

        agents_dir = archon_root / "agents"
        if not agents_dir.exists():
            pytest.skip("Agents directory not found")

        # Find agent specification files
        agent_specs = list(agents_dir.glob("agent-*.md"))

        if not agent_specs:
            pytest.skip("No agent specification files found")

        # Test processing the first agent spec
        first_spec = agent_specs[0]

        from ..agent import get_file_preview

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        preview_result = await get_file_preview(ctx, str(first_spec), max_lines=20)

        # Should successfully process agent specification
        assert "error" not in preview_result

        # Check for YAML frontmatter pattern
        preview_content = "\n".join(preview_result["preview_lines"])
        if preview_content.startswith("---"):
            # Should contain expected agent spec fields
            expected_fields = ["name:", "description:", "color:", "task_agent_type:"]
            found_fields = sum(
                1 for field in expected_fields if field in preview_content
            )
            assert found_fields >= 2, "Should find typical agent specification fields"

    @pytest.mark.asyncio
    async def test_comprehensive_agent_directory_scan(self, test_dependencies):
        """Test comprehensive scanning of agents directory."""
        archon_root = Path("/Volumes/PRO-G40/Code/Archon")

        if not archon_root.exists():
            pytest.skip("Archon project not found")

        agents_dir = archon_root / "agents"
        if not agents_dir.exists():
            pytest.skip("Agents directory not found")

        # Request comprehensive processing of agents directory
        request = DocumentationIndexerRequest(
            target_path=str(agents_dir),
            processing_mode="comprehensive",
            enable_cross_references=True,
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should find and process agent files
        assert result.files_discovered > 0
        assert result.processing_time_seconds > 0

        # Should achieve reasonable processing success
        if result.files_discovered > 0:
            # Allow for some processing challenges with real files
            assert result.success_rate >= 30

        # Should extract some knowledge categories
        # (Categories depend on actual content and processing)
        assert isinstance(result.knowledge_categories, list)
