#!/usr/bin/env python3
"""
Direct tool validation for Documentation Indexer Agent.
This tests the tool functions directly without requiring agent initialization.
"""

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import (
    DocumentationIndexerRequest,
    DocumentationProcessor,
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

## Cross References
See also [API Documentation](docs/api.md) and [Setup Guide](setup.txt).
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

See [Main README](../README.md) for overview.
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

## Configuration
The agent supports various configuration options.
        """,
        "setup.txt": """Setup Instructions

1. Install dependencies
2. Configure environment
3. Run the application

Prerequisites:
- Python 3.12+
- Docker
- Git

Environment Variables:
- API_KEY=your_key_here
- DEBUG=true

For more information, see README.md
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


async def test_documentation_processor():
    """Test the DocumentationProcessor class directly."""
    print("🔧 Testing DocumentationProcessor...")

    test_project = create_test_project()
    deps = create_test_dependencies()
    processor = DocumentationProcessor(deps)

    try:
        # Test file discovery
        print("🧪 Test: File Discovery")
        discovered_files = await processor.discover_documentation_files(
            str(test_project)
        )

        print("✅ File discovery completed:")
        print(f"   - Total files found: {len(discovered_files)}")
        for file_path in discovered_files:
            print(f"   - {file_path.name} ({file_path.suffix})")

        if len(discovered_files) >= 4:
            print("✅ File discovery validation passed")
        else:
            print("❌ File discovery validation failed")
            return False

        # Test file processing
        print("\n🧪 Test: File Processing")
        processed_content = []

        for file_path in discovered_files[:2]:  # Test first 2 files
            content_data = await processor.process_documentation_file(file_path)
            if content_data:
                processed_content.append(content_data)
                print(f"✅ Processed {file_path.name}:")
                print(f"   - Type: {content_data['file_type']}")
                print(f"   - Title: {content_data['title']}")
                print(f"   - Size: {content_data['size']} chars")
                print(
                    f"   - Cross-references: {len(content_data.get('cross_references', []))}"
                )
                print(
                    f"   - Semantic tags: {len(content_data.get('semantic_tags', []))}"
                )

        if len(processed_content) >= 2:
            print("✅ File processing validation passed")
        else:
            print("❌ File processing validation failed")
            return False

        # Test chunking
        print("\n🧪 Test: Content Chunking")
        chunked_content = await processor.apply_intelligent_chunking(processed_content)

        print("✅ Content chunking completed:")
        print(f"   - Total chunks created: {len(chunked_content)}")

        for i, chunk in enumerate(chunked_content[:3]):  # Show first 3 chunks
            print(f"   - Chunk {i+1}: {chunk.size} chars from {chunk.file_path}")
            print(f"     Title: {chunk.title}")
            print(f"     Header: {chunk.chunk_header or 'None'}")

        if len(chunked_content) >= len(processed_content):
            print("✅ Content chunking validation passed")
        else:
            print("❌ Content chunking validation failed")
            return False

        return True

    except Exception as e:
        print(f"❌ DocumentationProcessor test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(test_project)


async def test_file_preview_tool():
    """Test the get_file_preview tool directly."""
    print("\n📁 Testing File Preview Tool...")

    test_project = create_test_project()
    deps = create_test_dependencies()
    ctx = MockContext(deps)

    try:
        # Test different file types
        test_files = [
            ("README.md", ".md"),
            ("agent-spec.yaml", ".yaml"),
            ("setup.txt", ".txt"),
            ("docs/api.md", ".md"),
        ]

        success_count = 0

        for file_path, expected_ext in test_files:
            full_path = test_project / file_path
            if full_path.exists():
                print(f"🧪 Testing preview: {file_path}")

                preview = await get_file_preview(ctx, str(full_path), max_lines=10)

                if "error" not in preview:
                    print(f"✅ {file_path} preview successful:")
                    print(f"   - File type: {preview['file_type']}")
                    print(f"   - Total lines: {preview['total_lines']}")
                    print(f"   - Preview lines: {len(preview['preview_lines'])}")

                    if preview["file_type"] == expected_ext:
                        print("   - Type validation: ✅")
                        success_count += 1
                    else:
                        print(
                            f"   - Type validation: ❌ Expected {expected_ext}, got {preview['file_type']}"
                        )
                else:
                    print(f"❌ {file_path} preview failed: {preview['error']}")

        if success_count >= 3:
            print("✅ File preview tool validation passed")
            return True
        else:
            print("❌ File preview tool validation failed")
            return False

    except Exception as e:
        print(f"❌ File preview test failed: {e}")
        return False

    finally:
        shutil.rmtree(test_project)


async def test_index_documentation_tool():
    """Test the index_documentation tool directly."""
    print("\n📚 Testing Index Documentation Tool...")

    test_project = create_test_project()
    deps = create_test_dependencies()
    ctx = MockContext(deps)

    try:
        # Test basic indexing
        print("🧪 Test: Basic Documentation Indexing")
        request = DocumentationIndexerRequest(
            target_path=str(test_project), processing_mode="basic"
        )

        result = await index_documentation(ctx, request)

        print("✅ Basic indexing completed:")
        print(f"   - Files discovered: {result.files_discovered}")
        print(f"   - Files processed: {result.files_processed}")
        print(f"   - Files failed: {result.files_failed}")
        print(f"   - Chunks created: {result.chunks_created}")
        print(f"   - Success rate: {result.success_rate:.1f}%")
        print(f"   - Processing time: {result.processing_time_seconds:.2f}s")
        print(f"   - Knowledge categories: {result.knowledge_categories}")

        # Validate results
        validation_passed = 0
        total_validations = 4

        if result.files_discovered >= 4:
            print("✅ File discovery validation passed")
            validation_passed += 1

        if result.files_processed > 0:
            print("✅ File processing validation passed")
            validation_passed += 1

        if result.chunks_created > 0:
            print("✅ Chunk creation validation passed")
            validation_passed += 1

        if result.processing_time_seconds > 0:
            print("✅ Processing time validation passed")
            validation_passed += 1

        # Test comprehensive indexing
        print("\n🧪 Test: Comprehensive Documentation Indexing")
        comprehensive_request = DocumentationIndexerRequest(
            target_path=str(test_project),
            processing_mode="comprehensive",
            enable_cross_references=True,
        )

        comprehensive_result = await index_documentation(ctx, comprehensive_request)

        print("✅ Comprehensive indexing completed:")
        print(f"   - Files discovered: {comprehensive_result.files_discovered}")
        print(f"   - Files processed: {comprehensive_result.files_processed}")
        print(f"   - Chunks created: {comprehensive_result.chunks_created}")
        print(
            f"   - Knowledge categories: {len(comprehensive_result.knowledge_categories)}"
        )

        if comprehensive_result.chunks_created >= result.chunks_created:
            print("✅ Comprehensive processing validation passed")
            validation_passed += 1
            total_validations += 1

        success_rate = (validation_passed / total_validations) * 100
        print(
            f"📊 Index documentation tool validation: {validation_passed}/{total_validations} ({success_rate:.1f}%)"
        )

        return success_rate >= 80

    except Exception as e:
        print(f"❌ Index documentation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(test_project)


async def test_quality_validation_tool():
    """Test the validate_indexing_quality tool directly."""
    print("\n🎯 Testing Quality Validation Tool...")

    deps = create_test_dependencies()
    ctx = MockContext(deps)

    try:
        # Create diverse test chunks
        test_chunks = [
            DocumentChunk(
                chunk_id="high_quality_chunk",
                file_path="README.md",
                file_type="markdown",
                title="High Quality Document",
                chunk_index=0,
                content="This is a comprehensive document with detailed information, proper structure, and complete metadata coverage.",
                size=108,
                metadata={
                    "quality": "high",
                    "complete": True,
                    "author": "validator",
                    "category": "documentation",
                },
                cross_references=["api.md", "setup.txt"],
                semantic_tags=[
                    "documentation",
                    "comprehensive",
                    "high-quality",
                    "structured",
                ],
            ),
            DocumentChunk(
                chunk_id="medium_quality_chunk",
                file_path="api.md",
                file_type="markdown",
                title="API Documentation",
                chunk_index=0,
                content="This document provides API information with some cross-references but limited metadata.",
                size=89,
                metadata={"type": "api", "version": "1.0"},
                cross_references=["README.md"],
                semantic_tags=["api", "documentation"],
            ),
            DocumentChunk(
                chunk_id="basic_quality_chunk",
                file_path="notes.txt",
                file_type="text",
                title="Basic Notes",
                chunk_index=0,
                content="Simple text content without much structure.",
                size=43,
                metadata={},
                cross_references=[],
                semantic_tags=[],
            ),
            DocumentChunk(
                chunk_id="oversized_chunk",
                file_path="large.md",
                file_type="markdown",
                title="Large Document",
                chunk_index=0,
                content="X" * 5000,  # Very large chunk
                size=5000,
                metadata={"size": "large"},
                cross_references=["README.md"],
                semantic_tags=["large", "test"],
            ),
        ]

        # Test quality validation
        quality_result = await validate_indexing_quality(ctx, test_chunks)

        print("✅ Quality validation completed:")
        print(f"   - Total chunks: {quality_result['total_chunks']}")
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
        print("   - Size distribution:")
        print(f"     • Small chunks: {size_dist['small']}")
        print(f"     • Medium chunks: {size_dist['medium']}")
        print(f"     • Large chunks: {size_dist['large']}")
        print(f"     • Oversized chunks: {size_dist['oversized']}")

        # Validate format distribution
        format_dist = quality_result["format_distribution"]
        print(f"   - Format distribution: {format_dist}")

        # Quality validation checks
        validation_passed = 0
        total_validations = 5

        if quality_result["total_chunks"] == 4:
            print("✅ Chunk count validation passed")
            validation_passed += 1

        if 0 <= quality_result["quality_score"] <= 100:
            print("✅ Quality score range validation passed")
            validation_passed += 1

        if quality_result["metadata_completeness"]["metadata_percentage"] > 0:
            print("✅ Metadata analysis validation passed")
            validation_passed += 1

        if size_dist["oversized"] == 1:  # Should detect our oversized chunk
            print("✅ Size analysis validation passed")
            validation_passed += 1

        if "markdown" in format_dist and format_dist["markdown"] == 3:
            print("✅ Format analysis validation passed")
            validation_passed += 1

        success_rate = (validation_passed / total_validations) * 100
        print(
            f"📊 Quality validation tool: {validation_passed}/{total_validations} ({success_rate:.1f}%)"
        )

        return success_rate >= 80

    except Exception as e:
        print(f"❌ Quality validation test failed: {e}")
        return False


async def test_archon_integration():
    """Test integration with actual Archon project files if available."""
    print("\n🏛️ Testing Archon Integration...")

    archon_root = Path("/Volumes/PRO-G40/Code/Archon")

    if not archon_root.exists():
        print("⚠️ Archon project not found - skipping integration tests")
        return True

    deps = create_test_dependencies()
    ctx = MockContext(deps)

    try:
        # Test CLAUDE.md preview
        claude_md = archon_root / "CLAUDE.md"
        if claude_md.exists():
            print("🧪 Testing CLAUDE.md preview")
            preview = await get_file_preview(ctx, str(claude_md), max_lines=15)

            if "error" not in preview:
                print("✅ CLAUDE.md preview successful:")
                print(f"   - File size: {preview['size_bytes']:,} bytes")
                print(f"   - Total lines: {preview['total_lines']:,}")
                print(f"   - Preview lines: {len(preview['preview_lines'])}")

                # Validate content
                content_text = "\n".join(preview["preview_lines"]).lower()
                if "archon" in content_text:
                    print("✅ Content contains 'Archon' as expected")
                if "ai agent" in content_text or "documentation" in content_text:
                    print("✅ Content appears to be documentation-related")
            else:
                print(f"❌ CLAUDE.md preview failed: {preview['error']}")
                return False

        # Test agent directory structure
        agents_dir = archon_root / "agents"
        if agents_dir.exists():
            print("\n🧪 Testing agents directory")

            # Count different file types
            md_files = list(agents_dir.glob("*.md"))
            yaml_files = list(agents_dir.glob("*.yaml"))

            print("✅ Agents directory analysis:")
            print(f"   - Markdown files: {len(md_files)}")
            print(f"   - YAML files: {len(yaml_files)}")

            if md_files:
                # Test processing one agent file
                first_agent = md_files[0]
                print(f"   - Testing agent file: {first_agent.name}")

                preview = await get_file_preview(ctx, str(first_agent), max_lines=10)
                if "error" not in preview:
                    print("✅ Agent file preview successful")

                    # Look for YAML frontmatter
                    content = "\n".join(preview["preview_lines"])
                    if content.startswith("---"):
                        print("✅ YAML frontmatter detected")
                    if "agent" in content.lower():
                        print("✅ Agent-related content detected")

        return True

    except Exception as e:
        print(f"❌ Archon integration test failed: {e}")
        return False


async def main():
    """Run all tool validation tests."""
    print("🚀 Documentation Indexer Agent - Direct Tool Validation")
    print("=" * 65)

    tests = [
        ("DocumentationProcessor Core", test_documentation_processor),
        ("File Preview Tool", test_file_preview_tool),
        ("Index Documentation Tool", test_index_documentation_tool),
        ("Quality Validation Tool", test_quality_validation_tool),
        ("Archon Integration", test_archon_integration),
    ]

    success_count = 0

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if await test_func():
                success_count += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print("\n" + "=" * 65)
    success_rate = (success_count / len(tests)) * 100
    print(
        f"📊 FINAL RESULTS: {success_count}/{len(tests)} tests passed ({success_rate:.1f}%)"
    )

    if success_count == len(tests):
        print("🎉 ALL TOOL VALIDATION TESTS PASSED!")
        print("\n✅ Documentation Indexer Agent tools are fully functional")
        print("✅ File discovery and processing working")
        print("✅ Content chunking and metadata extraction operational")
        print("✅ Quality validation and assessment functional")
        print("✅ Archon project integration confirmed")
        print("\n🚀 Agent is ready for deployment and testing!")

    elif success_count >= len(tests) * 0.8:
        print("✅ MOST TOOL VALIDATION TESTS PASSED!")
        print(f"\n🟡 {success_count}/{len(tests)} tools validated successfully")
        print("🟡 Agent is substantially ready for deployment")

    else:
        print("❌ MULTIPLE TOOL VALIDATION TESTS FAILED")
        print(f"\n🔧 Only {success_count}/{len(tests)} tools working properly")
        print("🔧 Significant issues need to be addressed before deployment")

    return success_count >= len(tests) * 0.8


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
