"""
Test script for document chunking functionality.

This script tests the DocumentChunker utility and verifies that:
1. Token counting works correctly
2. Documents are chunked when they exceed the token limit
3. Chunk metadata is properly generated
4. Small documents are not unnecessarily chunked
"""

import asyncio
import sys
from pathlib import Path

# Add services/search to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.document_chunker import DocumentChunker


def test_token_counting():
    """Test token counting functionality"""
    print("\n" + "=" * 80)
    print("TEST 1: Token Counting")
    print("=" * 80)

    chunker = DocumentChunker(max_tokens=7500)

    # Test with short text
    short_text = "Hello, world!"
    token_count = chunker.count_tokens(short_text)
    print(f"Short text: '{short_text}'")
    print(f"Token count: {token_count}")
    assert token_count > 0, "Token count should be positive"

    # Test with longer text
    long_text = "This is a longer text. " * 100
    token_count = chunker.count_tokens(long_text)
    print(f"\nLong text: '{long_text[:50]}...'")
    print(f"Token count: {token_count}")
    assert token_count > 50, "Long text should have many tokens"

    print("✅ Token counting test passed!")


def test_no_chunking_needed():
    """Test that small documents are not chunked"""
    print("\n" + "=" * 80)
    print("TEST 2: No Chunking for Small Documents")
    print("=" * 80)

    chunker = DocumentChunker(max_tokens=7500)

    # Create a document that's well under the limit
    small_doc = "This is a small document. " * 50  # ~150 tokens
    token_count = chunker.count_tokens(small_doc)
    print(f"Document token count: {token_count}")

    needs_chunking = chunker.needs_chunking(small_doc)
    print(f"Needs chunking: {needs_chunking}")
    assert not needs_chunking, "Small document should not need chunking"

    chunks = chunker.chunk_document(small_doc, document_id="test-small")
    print(f"Number of chunks: {len(chunks)}")
    assert len(chunks) == 1, "Small document should result in 1 chunk"
    assert chunks[0]["chunk_index"] == 0, "Single chunk should have index 0"
    assert chunks[0]["total_chunks"] == 1, "Single chunk should report total_chunks=1"

    print("✅ No-chunking test passed!")


def test_chunking_large_document():
    """Test that large documents are properly chunked"""
    print("\n" + "=" * 80)
    print("TEST 3: Chunking Large Documents")
    print("=" * 80)

    chunker = DocumentChunker(max_tokens=500)  # Use small limit for testing

    # Create a large document that exceeds the limit
    large_doc = "This is a test sentence. " * 500  # ~2500 tokens
    token_count = chunker.count_tokens(large_doc)
    print(f"Document token count: {token_count}")

    needs_chunking = chunker.needs_chunking(large_doc)
    print(f"Needs chunking: {needs_chunking}")
    assert needs_chunking, "Large document should need chunking"

    chunks = chunker.chunk_document(large_doc, document_id="test-large")
    print(f"Number of chunks: {len(chunks)}")
    assert len(chunks) > 1, "Large document should be split into multiple chunks"

    # Verify chunk metadata
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1}:")
        print(f"  - chunk_index: {chunk['chunk_index']}")
        print(f"  - total_chunks: {chunk['total_chunks']}")
        print(f"  - token_count: {chunk['token_count']}")

        assert (
            chunk["chunk_index"] == i
        ), f"Chunk index mismatch: {chunk['chunk_index']} != {i}"
        assert chunk["total_chunks"] == len(
            chunks
        ), f"Total chunks mismatch: {chunk['total_chunks']} != {len(chunks)}"
        assert (
            chunk["token_count"] <= 500
        ), f"Chunk exceeds token limit: {chunk['token_count']} > 500"

    # Verify we can reconstruct the document from chunks
    # Note: semchunk may split at semantic boundaries, so we just verify we got reasonable chunks
    reconstructed = "".join([chunk["chunk_text"] for chunk in chunks])
    # Allow some tolerance for semantic chunking (within 10% of original)
    assert (
        len(reconstructed) >= len(large_doc) * 0.9
    ), f"Reconstructed document too short: {len(reconstructed)} < {len(large_doc) * 0.9}"

    print("✅ Chunking test passed!")


def test_chunk_metadata():
    """Test chunk metadata generation"""
    print("\n" + "=" * 80)
    print("TEST 4: Chunk Metadata Generation")
    print("=" * 80)

    chunker = DocumentChunker(max_tokens=300)
    doc = "Test sentence. " * 200  # ~400 tokens
    chunks = chunker.chunk_document(doc, document_id="test-meta")

    print(f"Generated {len(chunks)} chunks")

    for chunk in chunks:
        metadata = chunker.get_chunk_metadata(chunk, original_document_id="doc-123")

        print(f"\nChunk {chunk['chunk_index'] + 1} metadata:")
        for key, value in metadata.items():
            print(f"  - {key}: {value}")

        assert metadata["chunk_index"] == chunk["chunk_index"]
        assert metadata["total_chunks"] == chunk["total_chunks"]
        assert metadata["is_chunk"] is True
        assert metadata["parent_document_id"] == "doc-123"
        assert metadata["chunk_token_count"] == chunk["token_count"]

    print("✅ Metadata test passed!")


def test_realistic_code_file():
    """Test with a realistic code file"""
    print("\n" + "=" * 80)
    print("TEST 5: Realistic Code File")
    print("=" * 80)

    # Simulate a large Python file
    code_content = (
        '''
def example_function():
    """This is a docstring"""
    pass

class ExampleClass:
    """This is a class"""

    def __init__(self):
        self.value = 42

    def method(self):
        return self.value
'''
        * 200
    )  # Repeat to make it large

    chunker = DocumentChunker(max_tokens=1000)
    token_count = chunker.count_tokens(code_content)
    print(f"Code file token count: {token_count}")

    chunks = chunker.chunk_document(code_content, document_id="example.py")
    print(f"Number of chunks: {len(chunks)}")

    if len(chunks) > 1:
        print("✅ Large code file was chunked")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}: {chunk['token_count']} tokens")
    else:
        print("✅ Code file is small enough, no chunking needed")

    print("✅ Realistic code file test passed!")


def run_all_tests():
    """Run all chunking tests"""
    print("\n" + "=" * 80)
    print("DOCUMENT CHUNKING TEST SUITE")
    print("=" * 80)

    try:
        test_token_counting()
        test_no_chunking_needed()
        test_chunking_large_document()
        test_chunk_metadata()
        test_realistic_code_file()

        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        return True

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
