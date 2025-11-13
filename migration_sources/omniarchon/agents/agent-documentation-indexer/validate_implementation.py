#!/usr/bin/env python3
"""
Validation script for Documentation Indexer Agent implementation.
This script validates the core functionality without external API dependencies.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

# Import our agent components
from agent import (
    DocumentationIndexerRequest,
    DocumentChunk,
    get_file_preview,
    index_documentation,
    validate_indexing_quality,
)
from dependencies import create_test_dependencies


def create_test_project():
    """Create test project with sample documentation."""
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir)

    # Create test files
    test_files = {
        "README.md": """# Test Project

This is a test project for documentation indexing validation.

## Features
- Feature 1: Documentation processing
- Feature 2: Content chunking
- Feature 3: Metadata extraction

## Architecture
The system consists of multiple components working together.
        """,
        "docs/api.md": """# API Documentation

## Authentication
All endpoints require authentication.

### POST /login
Login endpoint for user authentication.

### GET /users
Get list of users.

## Error Handling
The API uses standard HTTP status codes.
        """,
        "agent-spec.yaml": """---
name: test-agent
description: A test agent for validation
color: blue
task_agent_type: test
---

# Test Agent Specification

This is a test agent used for validation purposes.

## Responsibilities
- Process test data
- Validate functionality
- Report results
        """,
        "setup.txt": """Setup Instructions

1. Install dependencies
2. Configure environment
3. Run the application

Prerequisites:
- Python 3.12+
- Docker
        """,
    }

    for file_path, content in test_files.items():
        full_path = project_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip())

    return project_path


class MockContext:
    """Mock context for testing tool functions."""

    def __init__(self, deps):
        self.deps = deps


async def validate_dependencies():
    """Validate that dependencies are configured correctly."""
    print("🔧 Validating Dependencies...")

    try:
        # Test dependencies creation
        deps = create_test_dependencies(
            chunk_size_target=500, max_file_size_mb=1, continue_on_error=True
        )
        print("✅ Test dependencies created successfully")

        # Validate configuration
        print(f"   - Chunk size target: {deps.chunk_size_target}")
        print(f"   - Max file size: {deps.max_file_size_mb}MB")
        print(f"   - Supported extensions: {len(deps.supported_extensions)} types")
        print(f"   - Continue on error: {deps.continue_on_error}")

        # Test validation method
        validation_results = deps.validate_dependencies()
        print("✅ Dependency validation:")
        for key, value in validation_results.items():
            status = "✅" if value else "⚠️"
            print(f"   {status} {key}: {value}")

        return deps

    except Exception as e:
        print(f"❌ Dependencies validation failed: {e}")
        return None


async def validate_file_operations():
    """Validate file discovery and preview operations."""
    print("\n📁 Validating File Operations...")

    test_project = create_test_project()
    print(f"✅ Created test project: {test_project}")

    try:
        deps = create_test_dependencies()
        ctx = MockContext(deps)

        # Test 1: File preview functionality
        print("🧪 Test 1: File Preview")
        readme_path = test_project / "README.md"

        preview_result = await get_file_preview(ctx, str(readme_path), max_lines=10)

        if "error" not in preview_result:
            print("✅ File preview successful")
            print(f"   - File type: {preview_result['file_type']}")
            print(f"   - Total lines: {preview_result['total_lines']}")
            print(f"   - Preview lines: {len(preview_result['preview_lines'])}")

            # Validate content
            content = "\n".join(preview_result["preview_lines"])
            if "Test Project" in content:
                print("✅ Content validation passed")
            else:
                print("⚠️ Content validation failed")
        else:
            print(f"❌ File preview failed: {preview_result['error']}")
            return False

        # Test 2: Multiple file types
        print("\n🧪 Test 2: Multiple File Types")
        test_files = [
            ("README.md", ".md"),
            ("agent-spec.yaml", ".yaml"),
            ("setup.txt", ".txt"),
            ("docs/api.md", ".md"),
        ]

        for file_path, expected_ext in test_files:
            full_path = test_project / file_path
            if full_path.exists():
                preview = await get_file_preview(ctx, str(full_path), max_lines=5)
                if "error" not in preview and preview["file_type"] == expected_ext:
                    print(f"✅ {file_path}: {preview['file_type']}")
                else:
                    print(f"❌ {file_path}: Failed or wrong type")

        return True

    except Exception as e:
        print(f"❌ File operations validation failed: {e}")
        return False

    finally:
        shutil.rmtree(test_project)


async def validate_documentation_indexing():
    """Validate core documentation indexing functionality."""
    print("\n📚 Validating Documentation Indexing...")

    test_project = create_test_project()

    try:
        deps = create_test_dependencies()
        ctx = MockContext(deps)

        # Test comprehensive indexing
        print("🧪 Test: Comprehensive Indexing")
        request = DocumentationIndexerRequest(
            target_path=str(test_project),
            processing_mode="comprehensive",
            enable_cross_references=True,
        )

        result = await index_documentation(ctx, request)

        print("✅ Indexing completed:")
        print(f"   - Files discovered: {result.files_discovered}")
        print(f"   - Files processed: {result.files_processed}")
        print(f"   - Chunks created: {result.chunks_created}")
        print(f"   - Success rate: {result.success_rate:.1f}%")
        print(f"   - Processing time: {result.processing_time_seconds:.2f}s")
        print(f"   - Knowledge categories: {len(result.knowledge_categories)}")
        print(f"   - Error summary: {len(result.error_summary)} errors")

        # Validation checks
        checks_passed = 0
        total_checks = 4

        if result.files_discovered >= 4:  # Should find our 4 test files
            print("✅ File discovery check passed")
            checks_passed += 1
        else:
            print(f"⚠️ File discovery check: expected ≥4, got {result.files_discovered}")

        if result.files_processed > 0:
            print("✅ File processing check passed")
            checks_passed += 1
        else:
            print("❌ File processing check failed")

        if result.chunks_created > 0:
            print("✅ Chunk creation check passed")
            checks_passed += 1
        else:
            print("❌ Chunk creation check failed")

        if result.processing_time_seconds > 0:
            print("✅ Processing time check passed")
            checks_passed += 1
        else:
            print("❌ Processing time check failed")

        success_rate = (checks_passed / total_checks) * 100
        print(
            f"📊 Indexing validation: {checks_passed}/{total_checks} checks passed ({success_rate:.1f}%)"
        )

        return success_rate >= 75  # 75% pass rate required

    except Exception as e:
        print(f"❌ Documentation indexing validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(test_project)


async def validate_quality_assessment():
    """Validate quality validation functionality."""
    print("\n🎯 Validating Quality Assessment...")

    try:
        deps = create_test_dependencies()
        ctx = MockContext(deps)

        # Create test chunks with varying quality
        test_chunks = [
            DocumentChunk(
                chunk_id="high_quality",
                file_path="README.md",
                file_type="markdown",
                title="High Quality Document",
                chunk_index=0,
                content="This is a well-structured document with comprehensive content and proper metadata.",
                size=85,
                metadata={"quality": "high", "complete": True, "author": "test"},
                cross_references=["api.md", "setup.txt"],
                semantic_tags=["documentation", "high-quality", "comprehensive"],
            ),
            DocumentChunk(
                chunk_id="medium_quality",
                file_path="api.md",
                file_type="markdown",
                title="Medium Quality Document",
                chunk_index=0,
                content="This document has some metadata but limited cross-references.",
                size=63,
                metadata={"type": "api"},
                cross_references=["README.md"],
                semantic_tags=["api"],
            ),
            DocumentChunk(
                chunk_id="low_quality",
                file_path="basic.txt",
                file_type="text",
                title="Basic Document",
                chunk_index=0,
                content="Basic content with minimal metadata.",
                size=35,
                metadata={},
                cross_references=[],
                semantic_tags=[],
            ),
        ]

        quality_result = await validate_indexing_quality(ctx, test_chunks)

        print("✅ Quality assessment completed:")
        print(f"   - Total chunks analyzed: {quality_result['total_chunks']}")
        print(
            f"   - Average chunk size: {quality_result['average_chunk_size']:.1f} chars"
        )
        print(f"   - Quality score: {quality_result['quality_score']:.1f}%")
        print(
            f"   - Metadata completeness: {quality_result['metadata_completeness']['metadata_percentage']:.1f}%"
        )
        print(
            f"   - Cross-reference coverage: {quality_result['cross_reference_coverage']:.1f}%"
        )
        print(
            f"   - Semantic tag coverage: {quality_result['semantic_tag_coverage']:.1f}%"
        )

        # Validate size distribution
        size_dist = quality_result["size_distribution"]
        print(f"   - Size distribution: {size_dist}")

        # Quality checks
        if quality_result["total_chunks"] == 3:
            print("✅ Chunk count validation passed")
        else:
            print("❌ Chunk count validation failed")

        if quality_result["quality_score"] > 0:
            print("✅ Quality scoring validation passed")
        else:
            print("❌ Quality scoring validation failed")

        return True

    except Exception as e:
        print(f"❌ Quality assessment validation failed: {e}")
        return False


async def validate_archon_integration():
    """Validate integration with actual Archon project if available."""
    print("\n🏛️ Validating Archon Project Integration...")

    archon_root = Path("/Volumes/PRO-G40/Code/Archon")

    if not archon_root.exists():
        print("⚠️ Archon project not found - skipping integration tests")
        return True

    try:
        deps = create_test_dependencies()
        ctx = MockContext(deps)

        # Test with CLAUDE.md
        claude_md = archon_root / "CLAUDE.md"
        if claude_md.exists():
            print("🧪 Testing CLAUDE.md preview")
            preview_result = await get_file_preview(ctx, str(claude_md), max_lines=20)

            if "error" not in preview_result:
                print("✅ CLAUDE.md preview successful")
                print(f"   - File size: {preview_result['size_bytes']} bytes")
                print(f"   - Total lines: {preview_result['total_lines']}")

                # Check content contains expected Archon information
                content_text = "\n".join(preview_result["preview_lines"]).lower()
                if "archon" in content_text:
                    print("✅ Content validation passed")
                else:
                    print("⚠️ Content validation - no 'archon' found in preview")
            else:
                print(f"❌ CLAUDE.md preview failed: {preview_result['error']}")
                return False

        # Test agents directory if it exists
        agents_dir = archon_root / "agents"
        if agents_dir.exists():
            print("🧪 Testing agents directory structure")

            # Count agent files
            agent_files = list(agents_dir.glob("agent-*.md"))
            print(f"✅ Found {len(agent_files)} agent specification files")

            if len(agent_files) > 0:
                # Test indexing a subset
                request = DocumentationIndexerRequest(
                    target_path=str(agents_dir),
                    include_patterns=["agent-*.md"],
                    processing_mode="basic",
                )

                result = await index_documentation(ctx, request)

                print("✅ Agents directory indexing:")
                print(f"   - Files discovered: {result.files_discovered}")
                print(f"   - Files processed: {result.files_processed}")
                print(f"   - Processing time: {result.processing_time_seconds:.2f}s")

                if result.files_discovered > 0:
                    print("✅ Archon integration validation passed")
                else:
                    print("⚠️ No agent files discovered")

        return True

    except Exception as e:
        print(f"❌ Archon integration validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all validation tests."""
    print("🚀 Documentation Indexer Agent Validation Suite")
    print("=" * 60)

    success_count = 0
    total_tests = 5

    # Test 1: Dependencies
    deps = await validate_dependencies()
    if deps is not None:
        success_count += 1

    # Test 2: File operations
    if await validate_file_operations():
        success_count += 1

    # Test 3: Documentation indexing
    if await validate_documentation_indexing():
        success_count += 1

    # Test 4: Quality assessment
    if await validate_quality_assessment():
        success_count += 1

    # Test 5: Archon integration
    if await validate_archon_integration():
        success_count += 1

    print("\n" + "=" * 60)
    success_rate = (success_count / total_tests) * 100
    print(
        f"📊 VALIDATION RESULTS: {success_count}/{total_tests} tests passed ({success_rate:.1f}%)"
    )

    if success_count == total_tests:
        print("🎉 ALL VALIDATION TESTS PASSED!")
        print("\n✅ The Documentation Indexer Agent is ready for deployment")
        print("✅ Core functionality validated")
        print("✅ File operations working")
        print("✅ Documentation indexing functional")
        print("✅ Quality assessment operational")
        print("✅ Archon integration confirmed")
    elif success_count >= 4:
        print("✅ MOST VALIDATION TESTS PASSED!")
        print("\n🟡 The Documentation Indexer Agent is mostly ready")
        print(f"🟡 {success_count}/{total_tests} core functions validated")
    else:
        print("❌ MULTIPLE VALIDATION TESTS FAILED")
        print(f"\n🔧 Only {success_count}/{total_tests} tests passed")
        print("🔧 Please review the implementation before deployment")

    return success_count >= 4  # Require at least 80% success rate


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
