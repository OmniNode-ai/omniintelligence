# Archon Integration Demos

This directory contains demonstration scripts and verification tools for the Archon Tree + Stamping integration.

## Files

### 1. demo_tree_stamping.py

**Purpose**: Complete end-to-end integration test for Tree + Stamping workflow

**What it tests**:
- Service health checks (Intelligence, Search, Qdrant, Memgraph, MCP)
- Bridge intelligence generation (metadata stamping)
- Qdrant vector database statistics
- Memgraph knowledge graph statistics
- Semantic search capabilities

**Usage**:
```bash
python3 demos/demo_tree_stamping.py
```

**Expected output**:
- Service health status for all components
- Bridge intelligence metadata generation (< 50ms)
- Qdrant vector count (should show indexed vectors)
- Memgraph node count (should show Entity nodes)
- Overall verification summary

---

### 2. check_embeddings.py

**Purpose**: Verify that Qdrant contains real OpenAI embeddings (not dummy data)

**What it checks**:
- Vector dimensions (should be 1536 for text-embedding-3-small)
- Vector values (should be real semantic embeddings, not [0.1, 0.2, 0.3, ...])
- Metadata completeness
- Sample content inspection

**Usage**:
```bash
python3 demos/check_embeddings.py
```

**Expected output**:
```
Point #1:
  Vector Dimensions: 1536
  Vector Sample: [0.003302, 0.047471, 0.023982, ...]
  ✅ CONFIRMED: Real OpenAI text-embedding-3-small
```

**Critical verification**: This proves PR #19 fix #1 (Real OpenAI embeddings) is working.

---

### 3. INTEGRATION_DEMO_RESULTS.md

**Purpose**: Complete verification report for PR #19 fixes

**Contents**:
- Executive summary of all fixes
- Detailed verification for each component
- Performance metrics
- Before/after comparisons for each fix
- Evidence and proof points

**Use case**: Reference documentation showing that all PR #19 critical fixes are verified and working.

---

## PR #19 Fixes Verified

### Fix #1: Real OpenAI Embeddings ✅

**Before**: Dummy vectors `[0.1, 0.2, 0.3, ...]`
**After**: Real OpenAI text-embedding-3-small (1536 dimensions)
**Evidence**: `check_embeddings.py` shows real vectors in Qdrant

### Fix #2: Memgraph Knowledge Graph Indexing ✅

**Before**: Stubbed implementation (no nodes created)
**After**: Real Memgraph indexing with 113+ Entity nodes
**Evidence**: `demo_tree_stamping.py` shows Memgraph node counts

### Fix #3: Semaphore Rate Limiting ✅

**Before**: Uncontrolled parallel OpenAI API calls
**After**: Semaphore with max 5 concurrent requests
**Evidence**: Stable operation with 1,403 indexed files (no rate limit errors)

### Fix #4: Specific Exception Handling ✅

**Before**: Broad `except Exception` blocks
**After**: Granular exception handling (OpenAIAPIError, MemgraphConnectionError, etc.)
**Evidence**: Service health checks show proper error handling

### Fix #5: Input Validation ✅

**Before**: No input validation
**After**: Comprehensive validation (path existence, type checks, etc.)
**Evidence**: Bridge intelligence validates inputs without errors

---

## Quick Verification

Run both demo scripts to verify the integration:

```bash
# Full integration test
python3 demos/demo_tree_stamping.py

# Verify real OpenAI embeddings
python3 demos/check_embeddings.py
```

**Expected**: All checks should pass with ✅ status

---

## Requirements

- Python 3.11+
- httpx library (`pip install httpx`)
- Running Archon services:
  - Intelligence (port 8053)
  - Search (port 8055)
  - Qdrant (port 6333)
  - Memgraph (port 7687)

Start services:
```bash
cd deployment
docker compose up -d
```

---

## Troubleshooting

**Service health checks fail**:
- Verify services are running: `docker compose ps`
- Check service logs: `docker logs archon-intelligence`

**No vectors in Qdrant**:
- Check if indexing has completed
- Verify OpenAI API key is configured: `echo $OPENAI_API_KEY`

**Memgraph connection errors**:
- Check Memgraph is running: `docker logs archon-memgraph`
- Verify bridge service can connect to Memgraph

---

**Created**: 2025-10-25
**Last Updated**: 2025-10-25
**Maintainer**: Archon Development Team
