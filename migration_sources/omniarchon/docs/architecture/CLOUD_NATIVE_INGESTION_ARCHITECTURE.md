# Cloud-Native Bulk Repository Ingestion Architecture

**Status**: Proposal
**Created**: 2025-10-28
**Author**: Archon Intelligence Team
**Version**: 1.0.0

---

## Executive Summary

Design a cloud-native architecture for bulk repository ingestion that eliminates filesystem mount dependencies, enabling deployment in any environment (local dev, CI/CD, cloud) with support for multiple content delivery strategies optimized for cost and performance.

**Key Problems Solved**:
- ✅ Remove dependency on local filesystem mounts in containers
- ✅ Enable ingestion from any environment (local, CI/CD, cloud)
- ✅ Support multiple content sources (local files, Git, S3, artifacts)
- ✅ Optimize for file size (inline small files, storage for large files)
- ✅ Maintain existing Kafka event architecture
- ✅ Backward compatible migration path

---

## Current Architecture Problems

### Problem 1: Filesystem Mount Dependency

**Current Flow**:
```
┌─────────────────┐     ┌────────────┐     ┌──────────────────┐
│ bulk_ingest.py  │────>│   Kafka    │────>│ Intelligence Svc │
│ (local machine) │     │            │     │   (Docker)       │
└─────────────────┘     └────────────┘     └──────────────────┘
        │                                            │
        │ Reads files at:                           │ Reads files at:
        │ /Volumes/PRO-G40/Code/repo                │ /mnt/code/repo ❌
        └───────────────────────────────────────────┘
                    Requires volume mount
```

**Issues**:
- ❌ Intelligence service needs `/Volumes/PRO-G40/Code` mounted into container
- ❌ Paths are environment-specific (dev machine paths)
- ❌ Doesn't work in cloud where local directories don't exist
- ❌ Can't ingest from remote sources without cloning first
- ❌ CI/CD pipelines need complex volume mounting

### Problem 2: Current Event Schema

**Current Message** (`dev.archon-intelligence.tree.index-project-requested.v1`):
```json
{
  "payload": {
    "project_name": "omniarchon",
    "project_path": "/Volumes/PRO-G40/Code/omniarchon",  // ❌ Local path
    "files": [
      {
        "file_path": "/Volumes/PRO-G40/Code/omniarchon/src/api.py",  // ❌ Local path
        "relative_path": "src/api.py",
        "language": "python",
        "size_bytes": 15234
      }
    ]
  }
}
```

**Issues**:
- File paths are absolute local paths (environment-specific)
- No file content included (requires filesystem access)
- Service falls back to reading from mounted filesystem

### Problem 3: Current Service Implementation

**Bridge Intelligence Generator** (`_get_file_content()`):
```python
async def _get_file_content(self, file_path: str, provided_content: Optional[str]):
    if provided_content:
        return provided_content, len(provided_content.encode("utf-8"))

    # ❌ Falls back to reading from filesystem
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8")
            return content, path.stat().st_size
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")

    return None, 0
```

**Key Insight**: Service **already supports** `provided_content` parameter! We just need to populate it.

---

## Proposed Architecture: Hybrid Content Delivery

### Design Philosophy

**Multi-Strategy Approach**: Support three content delivery methods, selecting the optimal strategy based on file size, source, and environment.

```
┌──────────────────────────────────────────────────────────────┐
│                    CONTENT STRATEGY SELECTOR                  │
│                                                                │
│  IF file_size < 100KB AND source=local                       │
│    → INLINE_CONTENT (in Kafka message)                       │
│                                                                │
│  ELSE IF source=git                                           │
│    → GIT_REFERENCE (url + commit + path)                     │
│                                                                │
│  ELSE IF file_size > 100KB OR source=cloud                   │
│    → OBJECT_STORAGE (S3/GCS/MinIO URL)                       │
│                                                                │
│  ELSE                                                          │
│    → INLINE_CONTENT (fallback)                               │
└──────────────────────────────────────────────────────────────┘
```

### Strategy 1: Inline Content (Small Files)

**Use Case**: Files <100KB, local development, small codebases

**Flow**:
```
┌─────────────────┐     ┌────────────┐     ┌──────────────────┐
│ bulk_ingest.py  │────>│   Kafka    │────>│ Intelligence Svc │
│                 │     │ Message:   │     │                  │
│ Reads file      │     │ {content:  │     │ Uses content     │
│ content inline  │     │  "def..."}│     │ directly         │
└─────────────────┘     └────────────┘     └──────────────────┘
```

**Pros**:
- ✅ Simple implementation (no external dependencies)
- ✅ Fast (no network roundtrips)
- ✅ Works everywhere (no cloud storage needed)
- ✅ Good for development environments

**Cons**:
- ❌ Kafka message size limits (10MB practical max)
- ❌ High memory usage for large batches
- ❌ Not suitable for large files (images, binaries, large docs)

**Cost**: Free (Kafka storage only)

**Performance**: ~5-50ms (direct content access)

**Example Message**:
```json
{
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "files": [
      {
        "relative_path": "src/api.py",
        "language": "python",
        "size_bytes": 15234,
        "content_strategy": "inline",
        "content": "def hello():\n    print('hello')\n...",  // ✅ Inline
        "content_encoding": "utf-8",
        "checksum": "sha256:abc123..."
      }
    ]
  }
}
```

### Strategy 2: Object Storage URLs (Large Files)

**Use Case**: Files >100KB, production deployments, cloud environments, CI/CD

**Flow**:
```
┌─────────────────┐     ┌────────────┐     ┌──────────────────┐
│ bulk_ingest.py  │────>│   Kafka    │────>│ Intelligence Svc │
│                 │     │ Message:   │     │                  │
│ 1. Upload to S3 │     │ {url: s3://│     │ 1. Download from │
│ 2. Send URL     │     │  bucket/..}│     │    S3            │
└─────────────────┘     └────────────┘     │ 2. Process       │
        │                                   └──────────────────┘
        ↓
┌─────────────────┐
│  S3/GCS/MinIO   │<──────────────────────────────────────────┘
│  Object Storage │
└─────────────────┘
```

**Pros**:
- ✅ Unlimited file sizes (no Kafka limits)
- ✅ Cloud-native (works in any environment)
- ✅ Cost-effective storage ($0.023/GB/month S3)
- ✅ Built-in versioning and lifecycle management
- ✅ Supports presigned URLs (security)
- ✅ Can serve as permanent artifact storage

**Cons**:
- ❌ Requires cloud storage account (S3/GCS/MinIO)
- ❌ Network latency (upload + download)
- ❌ Storage costs (minimal but non-zero)
- ❌ More complex setup

**Cost**: ~$0.023/GB/month (S3 Standard) + $0.09/GB transfer

**Performance**: ~100-500ms (upload + download latency)

**Example Message**:
```json
{
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "files": [
      {
        "relative_path": "assets/large_dataset.json",
        "language": "json",
        "size_bytes": 5242880,
        "content_strategy": "object_storage",
        "content_url": "s3://archon-artifacts/projects/omniarchon/abc123.json",
        "content_url_type": "s3",
        "content_url_expires_at": "2025-10-29T00:00:00Z",  // Presigned URL expiry
        "checksum": "sha256:def456..."
      }
    ]
  }
}
```

### Strategy 3: Git References (Git Repositories)

**Use Case**: Public/private Git repositories, continuous integration, version tracking

**Flow**:
```
┌─────────────────┐     ┌────────────┐     ┌──────────────────┐
│ bulk_ingest.py  │────>│   Kafka    │────>│ Intelligence Svc │
│                 │     │ Message:   │     │                  │
│ Send Git URL    │     │ {git_url:  │     │ 1. Clone repo    │
│ + commit SHA    │     │  commit}   │     │ 2. Read file     │
└─────────────────┘     └────────────┘     │ 3. Cache clone   │
                                            └──────────────────┘
```

**Pros**:
- ✅ Version control built-in (commit SHAs)
- ✅ Works with any Git repository (public/private)
- ✅ No need to clone locally first
- ✅ Efficient delta updates (only changed files)
- ✅ Natural fit for continuous ingestion

**Cons**:
- ❌ Git dependency in intelligence service
- ❌ Clone time for large repos (GB-sized repos = minutes)
- ❌ Requires credential management for private repos
- ❌ Not suitable for non-Git sources

**Cost**: Free (Git hosting costs only)

**Performance**:
- Cold: ~5-60s (initial clone, size-dependent)
- Warm: ~50-200ms (cached clone + file read)

**Example Message**:
```json
{
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "content_strategy": "git_reference",
    "git_url": "https://github.com/user/repo.git",
    "git_ref": "abc123def456...",  // Commit SHA
    "git_branch": "main",
    "files": [
      {
        "relative_path": "src/api.py",
        "language": "python",
        "size_bytes": 15234,
        "checksum": "sha256:abc123..."
      }
    ]
  }
}
```

---

## Event Schema v2.0.0: Phase 1 (Inline Content)

### Overview

Event schema v2.0.0 introduces inline content support, eliminating filesystem mount dependencies. Phase 1 focuses on inline content delivery for files <100KB.

**Schema Version**: `2.0.0`
**Status**: Phase 1 Implementation
**Backward Compatible**: Yes (services support v1 + v2)

### Core Schema Changes

**New Required Field**:
- `schema_version`: String indicating event schema version (e.g., "2.0.0")

**New File Fields**:
- `content`: String containing file content (UTF-8 encoded text)
- `content_strategy`: Enum indicating delivery method ("inline", "object_storage", "git_reference")
- `checksum`: String with hash type and value (e.g., "sha256:abc123..." or "blake3:def456...")

**Modified Fields**:
- `project_path`: Now optional (can be null for cloud environments)
- `file_path`: Deprecated (replaced by `relative_path` + `content`)
- `relative_path`: Now primary identifier (environment-agnostic)

### Field Documentation

| Field | Type | Required | Phase | Description |
|-------|------|----------|-------|-------------|
| `schema_version` | string | Yes | 1 | Event schema version (e.g., "2.0.0") |
| `content` | string | Phase 1 | 1 | File content (UTF-8 text). Required for inline strategy. |
| `content_strategy` | enum | Yes | 1 | Delivery method: "inline" (Phase 1), "object_storage" (Phase 2), "git_reference" (Phase 3) |
| `content_encoding` | string | Phase 1 | 1 | Content encoding (default: "utf-8"). Required when content is present. |
| `checksum` | string | Yes | 1 | Content verification hash. Format: "{algorithm}:{hash}" (e.g., "sha256:abc123") |
| `relative_path` | string | Yes | 1 | Path relative to project root (environment-agnostic) |
| `absolute_path` | string | No | 1 | Original absolute path (metadata only, for backward compatibility) |
| `content_url` | string | Phase 2 | 2 | Object storage URL (S3/GCS/MinIO). Required for object_storage strategy. |
| `content_url_type` | enum | Phase 2 | 2 | Storage provider: "s3", "gcs", "minio" |
| `content_url_expires_at` | ISO8601 | Phase 2 | 2 | Presigned URL expiration timestamp |
| `git_url` | string | Phase 3 | 3 | Git repository URL. Required for git_reference strategy. |
| `git_ref` | string | Phase 3 | 3 | Git commit SHA. Required for git_reference strategy. |

### Phase 1 Event Schema (Inline Content Only)

**Event Type**: `dev.archon-intelligence.tree.index-project-requested.v2`

**Minimal Phase 1 Example**:
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v2",
  "correlation_id": "7a8b9c0d-1234-5678-90ab-cdef12345678",
  "timestamp": "2025-10-28T12:00:00Z",
  "schema_version": "2.0.0",
  "source": {
    "service": "bulk-ingest-cli",
    "instance_id": "batch-0"
  },
  "metadata": {
    "batch_id": 0,
    "batch_size": 2,
    "content_strategy": "inline",
    "total_content_size_bytes": 45678
  },
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "content_strategy": "inline",
    "files": [
      {
        "relative_path": "src/api.py",
        "absolute_path": "/Volumes/PRO-G40/Code/omniarchon/src/api.py",
        "language": "python",
        "size_bytes": 15234,
        "last_modified": "2025-10-28T11:00:00Z",
        "content_strategy": "inline",
        "content": "\"\"\"API module for Omniarchon.\"\"\"\n\ndef hello_world():\n    return {\"message\": \"Hello, World!\"}",
        "content_encoding": "utf-8",
        "checksum": "sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
      },
      {
        "relative_path": "src/models.py",
        "absolute_path": "/Volumes/PRO-G40/Code/omniarchon/src/models.py",
        "language": "python",
        "size_bytes": 30444,
        "last_modified": "2025-10-28T10:30:00Z",
        "content_strategy": "inline",
        "content": "\"\"\"Data models.\"\"\"\nfrom pydantic import BaseModel\n\nclass User(BaseModel):\n    id: int\n    name: str",
        "content_encoding": "utf-8",
        "checksum": "sha256:b2c3d4e5f67890123456789012345678901234567890abcdef1234567890abcd"
      }
    ],
    "include_tests": true,
    "force_reindex": false
  }
}
```

### Migration: v1.0.0 → v2.0.0

#### Before (v1.0.0) - Filesystem Dependent

**Event Type**: `dev.archon-intelligence.tree.index-project-requested.v1`

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v1",
  "correlation_id": "7a8b9c0d-1234-5678-90ab-cdef12345678",
  "timestamp": "2025-10-28T12:00:00Z",
  "payload": {
    "project_name": "omniarchon",
    "project_path": "/Volumes/PRO-G40/Code/omniarchon",
    "files": [
      {
        "file_path": "/Volumes/PRO-G40/Code/omniarchon/src/api.py",
        "relative_path": "src/api.py",
        "language": "python",
        "size_bytes": 15234
      }
    ]
  }
}
```

**Problems**:
- ❌ `file_path` contains environment-specific absolute path
- ❌ `project_path` requires filesystem mount in consumer
- ❌ No content included - consumer must read from filesystem
- ❌ No schema version field
- ❌ No content verification (checksum)

#### After (v2.0.0) - Cloud-Native

**Event Type**: `dev.archon-intelligence.tree.index-project-requested.v2`

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v2",
  "correlation_id": "7a8b9c0d-1234-5678-90ab-cdef12345678",
  "timestamp": "2025-10-28T12:00:00Z",
  "schema_version": "2.0.0",
  "source": {
    "service": "bulk-ingest-cli",
    "instance_id": "batch-0"
  },
  "metadata": {
    "batch_id": 0,
    "batch_size": 1,
    "content_strategy": "inline",
    "total_content_size_bytes": 15234
  },
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "content_strategy": "inline",
    "files": [
      {
        "relative_path": "src/api.py",
        "absolute_path": "/Volumes/PRO-G40/Code/omniarchon/src/api.py",
        "language": "python",
        "size_bytes": 15234,
        "last_modified": "2025-10-28T11:00:00Z",
        "content_strategy": "inline",
        "content": "\"\"\"API module for Omniarchon.\"\"\"\n\ndef hello_world():\n    return {\"message\": \"Hello, World!\"}",
        "content_encoding": "utf-8",
        "checksum": "sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
      }
    ],
    "include_tests": true,
    "force_reindex": false
  }
}
```

**Improvements**:
- ✅ `schema_version` field enables versioning
- ✅ `content` field includes file content inline
- ✅ `content_strategy` indicates delivery method
- ✅ `checksum` enables content verification
- ✅ `project_path` is null (no filesystem dependency)
- ✅ `absolute_path` kept for metadata only (backward compatibility)
- ✅ `relative_path` is primary identifier (environment-agnostic)

### Key Differences Summary

| Aspect | v1.0.0 | v2.0.0 (Phase 1) |
|--------|--------|------------------|
| **Schema Version** | None | `"schema_version": "2.0.0"` |
| **Content Delivery** | Filesystem read | Inline in message |
| **Primary Path** | `file_path` (absolute) | `relative_path` |
| **Filesystem Dependency** | Required | None |
| **Content Verification** | None | SHA256/BLAKE3 checksum |
| **Cloud Compatible** | ❌ No | ✅ Yes |
| **Content Strategy** | Implicit | Explicit enum |
| **File Size Limit** | None (filesystem) | 100KB (Kafka limit) |

---

## Complete Event Schema (v2.0.0) - All Phases

### Backward-Compatible Schema

**New Event Type**: `dev.archon-intelligence.tree.index-project-requested.v2`

```json
{
  "event_id": "uuid",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v2",
  "correlation_id": "uuid",
  "timestamp": "2025-10-28T12:00:00Z",
  "version": "2.0.0",
  "source": {
    "service": "bulk-ingest-cli",
    "instance_id": "batch-0"
  },
  "metadata": {
    "batch_id": 0,
    "batch_size": 50,
    "content_strategy": "inline | object_storage | git_reference",
    "total_content_size_bytes": 1048576
  },
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,  // ✅ Optional now (not used in cloud)

    // Global content strategy (applies to all files unless overridden)
    "content_strategy": "inline",

    // Git reference (if content_strategy = "git_reference")
    "git_url": "https://github.com/user/repo.git",
    "git_ref": "abc123def456...",
    "git_branch": "main",
    "git_credentials": {  // Optional for private repos
      "type": "token | ssh_key",
      "credential_ref": "secret_manager_path"
    },

    // Object storage config (if content_strategy = "object_storage")
    "object_storage_config": {
      "provider": "s3 | gcs | minio",
      "bucket": "archon-artifacts",
      "region": "us-east-1",
      "endpoint": null  // Optional for MinIO
    },

    "files": [
      {
        // File metadata (always present)
        "relative_path": "src/api.py",
        "language": "python",
        "size_bytes": 15234,
        "checksum": "sha256:abc123...",
        "last_modified": "2025-10-28T11:00:00Z",

        // Content delivery (strategy-specific)
        "content_strategy": "inline",  // Can override global strategy

        // STRATEGY 1: Inline content
        "content": "def hello():\n    print('hello')\n...",  // If inline
        "content_encoding": "utf-8",

        // STRATEGY 2: Object storage URL
        "content_url": "s3://archon-artifacts/projects/omniarchon/abc123.py",  // If object_storage
        "content_url_type": "s3 | gcs | minio",
        "content_url_expires_at": "2025-10-29T00:00:00Z",  // Presigned URL

        // STRATEGY 3: Git reference (uses global git_url + relative_path)
        // No file-specific fields needed
      }
    ],

    "include_tests": true,
    "force_reindex": false
  }
}
```

### Schema Design Principles

1. **Backward Compatible**: v1 consumers ignore unknown fields
2. **Strategy Flexible**: Each file can use different strategy
3. **Environment Agnostic**: No hardcoded local paths
4. **Security Conscious**: Presigned URLs, credential references
5. **Verifiable**: Checksums for all content
6. **Metadata Rich**: Language, size, last_modified for all files

---

## Implementation Phases

### Phase 1: Inline Content Support (MVP) ✅

**Timeline**: 1-2 days
**Risk**: Low
**Value**: High (enables cloud deployment)

**Tasks**:
1. ✅ Update `batch_processor.py` to include file content inline
2. ✅ Update event schema to v2.0.0 with `content` field
3. ✅ Update `BridgeIntelligenceRequest` to support inline content
4. ✅ Update consumers to use `provided_content` instead of file_path
5. ✅ Add content size limits (100KB per file, 5MB per batch)
6. ✅ Test with small repositories (<100 files)

**Deliverables**:
- Updated `BatchProcessor._build_event()` to read and include file content
- Updated event schema documentation
- Integration tests with inline content
- Performance benchmarks (batch processing time)

**Code Changes**:
```python
# batch_processor.py
async def _build_event(self, ..., files: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Add file content inline for small files
    enriched_files = []
    for file_dict in files:
        file_path = Path(file_dict["file_path"])
        size_bytes = file_dict["size_bytes"]

        if size_bytes <= 100_000:  # 100KB threshold
            try:
                content = file_path.read_text(encoding="utf-8")
                enriched_file = {
                    **file_dict,
                    "content_strategy": "inline",
                    "content": content,
                    "content_encoding": "utf-8",
                }
                enriched_files.append(enriched_file)
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                enriched_files.append(file_dict)  # Skip file
        else:
            # Large file - skip for Phase 1
            logger.warning(f"File too large for inline: {file_path} ({size_bytes} bytes)")

    # ... rest of event building
```

### Phase 2: Object Storage Support (Production)

**Timeline**: 3-5 days
**Risk**: Medium
**Value**: High (enables large files, cloud artifacts)

**Tasks**:
1. Add S3/GCS/MinIO client to `bulk_ingest.py`
2. Implement upload logic with presigned URLs
3. Add object storage config to event schema
4. Update intelligence service to download from URLs
5. Implement caching layer (avoid re-downloading)
6. Add lifecycle policies (auto-delete after N days)
7. Security: presigned URLs, credential management
8. Test with large files (>100KB)

**Deliverables**:
- `ContentStorageClient` abstraction (S3/GCS/MinIO)
- Upload/download utilities with retry logic
- Presigned URL generation (secure, time-limited)
- Local cache for downloaded files (LRU eviction)
- Configuration guide for cloud storage setup

**Code Sketch**:
```python
# scripts/lib/content_storage.py
class ContentStorageClient:
    """Abstract interface for object storage"""

    async def upload_file(self, file_path: Path, object_key: str) -> str:
        """Upload file and return URL"""
        pass

    async def generate_presigned_url(self, object_key: str, expires_in: int) -> str:
        """Generate presigned URL for secure access"""
        pass

    async def download_file(self, url: str, dest_path: Path) -> None:
        """Download file from URL"""
        pass

class S3StorageClient(ContentStorageClient):
    """S3-specific implementation"""
    # ...

class MinIOStorageClient(ContentStorageClient):
    """MinIO-specific implementation (local dev)"""
    # ...
```

### Phase 3: Git Reference Support (Advanced)

**Timeline**: 5-7 days
**Risk**: High
**Value**: Medium (enables continuous ingestion)

**Tasks**:
1. Add Git client to intelligence service
2. Implement clone caching with LRU eviction
3. Add credential management (SSH keys, tokens)
4. Handle private repositories securely
5. Optimize: shallow clones, sparse checkout
6. Implement delta updates (only changed files)
7. Test with large repositories (>1GB)

**Deliverables**:
- `GitContentFetcher` service component
- Clone cache with TTL and size limits
- Credential management (Secret Manager integration)
- Delta ingestion workflow (only changed files)
- Performance optimizations (shallow clones)

**Code Sketch**:
```python
# services/intelligence/src/services/git_content_fetcher.py
class GitContentFetcher:
    """Fetch content from Git repositories with caching"""

    def __init__(self, cache_dir: Path, max_cache_size_gb: int = 50):
        self.cache_dir = cache_dir
        self.max_cache_size_gb = max_cache_size_gb
        self._clone_cache = {}  # {repo_url: {commit_sha: clone_path}}

    async def fetch_file_content(
        self,
        git_url: str,
        commit_sha: str,
        file_path: str,
        credentials: Optional[GitCredentials] = None
    ) -> str:
        """Fetch file content from Git repository"""

        # Check cache first
        cache_key = f"{git_url}:{commit_sha}"
        if cache_key in self._clone_cache:
            clone_path = self._clone_cache[cache_key]
            return (clone_path / file_path).read_text()

        # Clone repository (shallow)
        clone_path = await self._clone_repo(git_url, commit_sha, credentials)
        self._clone_cache[cache_key] = clone_path

        # Read file
        return (clone_path / file_path).read_text()

    async def _clone_repo(self, git_url: str, commit_sha: str, credentials) -> Path:
        """Clone repository with shallow depth"""
        # Implementation with git clone --depth 1 --branch <commit>
        pass
```

### Phase 4: Optimization & Monitoring

**Timeline**: 2-3 days
**Risk**: Low
**Value**: Medium (production readiness)

**Tasks**:
1. Add metrics: content strategy usage, latencies, costs
2. Implement automatic strategy selection (ML-based)
3. Add cost monitoring (S3 storage, transfer costs)
4. Performance tuning: compression, batch sizes
5. Add health checks for storage backends
6. Implement fallback strategies (object_storage → inline)

**Deliverables**:
- Prometheus metrics for content delivery
- Cost dashboard (storage, transfer, compute)
- Automatic strategy selector based on history
- Fallback logic for storage failures
- Performance benchmarks and recommendations

---

## Migration Strategy

### Gradual Rollout Plan

**Phase 1: Dual Support (v1 + v2)**
- Intelligence service supports both v1 (file_path) and v2 (content strategies)
- Publishers gradually migrate to v2
- No disruption to existing workflows

**Phase 2: v2 Default**
- New ingestion jobs use v2 by default
- v1 still supported for backward compatibility
- Monitoring shows v2 adoption rate

**Phase 3: v1 Deprecation**
- Announce v1 deprecation timeline
- Migrate remaining v1 publishers to v2
- Remove v1 support after grace period

### Backward Compatibility

**Intelligence Service Changes**:
```python
# bridge_intelligence_generator.py
async def _get_file_content(self, request: BridgeIntelligenceRequest) -> Tuple[Optional[str], int]:
    """Get file content from multiple sources (v1 + v2 compatible)"""

    # Priority 1: Inline content (v2)
    if request.content:
        return request.content, len(request.content.encode("utf-8"))

    # Priority 2: Object storage URL (v2)
    if request.content_url:
        content = await self._download_from_url(request.content_url)
        return content, len(content.encode("utf-8"))

    # Priority 3: Git reference (v2)
    if request.git_url and request.git_ref:
        content = await self._fetch_from_git(
            request.git_url, request.git_ref, request.relative_path
        )
        return content, len(content.encode("utf-8"))

    # Priority 4: Local file path (v1 fallback)
    if request.file_path:
        try:
            path = Path(request.file_path)
            if path.exists() and path.is_file():
                content = path.read_text(encoding="utf-8")
                return content, path.stat().st_size
        except Exception as e:
            logger.warning(f"v1 fallback failed for {request.file_path}: {e}")

    logger.error("No content source available")
    return None, 0
```

---

## Cost Analysis

### Strategy Comparison (Per 1000 Files, Avg 25KB/file)

| Strategy | Storage Cost | Transfer Cost | Compute Cost | Total/Month | Use Case |
|----------|--------------|---------------|--------------|-------------|----------|
| **Inline** | $0 | $0 | ~$2 | **$2** | Dev, small files |
| **S3** | $0.58 | $2.25 | ~$2 | **$4.83** | Production, large files |
| **Git** | $0 | $0 | ~$5 | **$5** | Continuous integration |

**Assumptions**:
- 1000 files/month, 25KB average size = 25MB total
- S3 Standard: $0.023/GB/month storage + $0.09/GB transfer
- Compute: Intelligence service processing costs
- Git: Higher compute (clone operations)

**Cost Optimization**:
- Use **inline** for files <100KB (majority of code files)
- Use **S3** only for large files >100KB (images, datasets, binaries)
- Use **Git** for continuous ingestion (delta updates)

**Real-World Example** (Omniarchon repository):
- 1000 files, avg 20KB = 20MB total
- 95% files <100KB → inline ($0 storage)
- 5% files >100KB → S3 ($0.03/month)
- **Total cost: ~$2/month** (mostly compute)

---

## Performance Analysis

### Latency Comparison (Per File Processing)

| Strategy | Upload Time | Download Time | Total Latency | Scalability |
|----------|-------------|---------------|---------------|-------------|
| **Inline** | N/A | N/A | **5-50ms** | ⚠️ Limited by Kafka message size |
| **S3** | 50-200ms | 50-200ms | **100-400ms** | ✅ Unlimited file sizes |
| **Git** (cold) | N/A | 5-60s | **5-60s** | ⚠️ Slow initial clone |
| **Git** (warm) | N/A | 50-200ms | **50-200ms** | ✅ Fast with cache |

### Throughput (Files/Second)

| Strategy | Batch Size 50 | Batch Size 100 | Batch Size 200 |
|----------|---------------|----------------|----------------|
| **Inline** | **500-1000** | **800-1500** | **1000-2000** |
| **S3** | 50-100 | 80-150 | 100-200 |
| **Git** (cold) | 1-5 | 2-8 | 3-10 |
| **Git** (warm) | 50-100 | 80-150 | 100-200 |

**Recommendations**:
- **Development**: Use inline (fast, simple)
- **Production**: Use hybrid (inline + S3 for large files)
- **CI/CD**: Use Git references (cache clones for speed)

---

## Security Considerations

### Content Security

**Inline Content**:
- ✅ No additional security concerns (content in Kafka)
- ✅ Kafka ACLs control message access
- ⚠️ Kafka message retention policy applies (default 7 days)

**Object Storage URLs**:
- ✅ Use presigned URLs (time-limited, scoped access)
- ✅ Expire URLs after 24 hours
- ✅ No public bucket access required
- ✅ Support IAM roles (no credentials in messages)
- ⚠️ URL leakage risk (if logged/exposed)

**Git References**:
- ✅ Support SSH keys and tokens
- ✅ Use Secret Manager for credentials
- ✅ No credentials in Kafka messages
- ⚠️ Clone cache may contain sensitive code

### Credential Management

**Recommended Approach**:
```json
{
  "git_credentials": {
    "type": "secret_manager_reference",
    "secret_path": "projects/archon/secrets/github-deploy-key",
    "version": "latest"
  }
}
```

**DO NOT**:
- ❌ Put raw credentials in Kafka messages
- ❌ Use long-lived access tokens (prefer short-lived or presigned URLs)
- ❌ Log presigned URLs or credentials

---

## Testing Strategy

### Unit Tests

**Phase 1: Inline Content**
- ✅ Test file content reading (various encodings)
- ✅ Test content size limits (100KB threshold)
- ✅ Test event schema serialization
- ✅ Test backward compatibility (v1 → v2)

**Phase 2: Object Storage**
- ✅ Test S3 upload/download
- ✅ Test presigned URL generation
- ✅ Test cache hit/miss scenarios
- ✅ Test storage backend failures

**Phase 3: Git References**
- ✅ Test Git clone operations
- ✅ Test credential handling (SSH, token)
- ✅ Test cache eviction policies
- ✅ Test shallow clone optimization

### Integration Tests

**End-to-End Scenarios**:
1. Ingest small repository (100 files) → All inline
2. Ingest large repository (1000 files, mixed sizes) → Hybrid (inline + S3)
3. Ingest from Git URL → Clone and process
4. Simulate storage failure → Fallback to inline
5. Test with large files (>10MB) → S3 only

**Performance Benchmarks**:
- Baseline: 1000 files, avg 25KB, <95s total
- Strategy comparison: inline vs S3 vs Git
- Scalability: 100, 1000, 10000 files
- Network sensitivity: low/high latency scenarios

### Load Tests

**Scenarios**:
- **Burst load**: 10 repositories ingested simultaneously
- **Sustained load**: 100 repositories/hour for 24 hours
- **Large repository**: Single repo with 10,000 files
- **Storage saturation**: S3 bucket with 100GB data

---

## Recommended Implementation Order

### Week 1: MVP (Inline Content)

**Days 1-2**:
- ✅ Update `batch_processor.py` to read file content
- ✅ Update event schema to v2.0.0
- ✅ Add content size validation (100KB limit)

**Days 3-4**:
- ✅ Update `BridgeIntelligenceRequest` model
- ✅ Update intelligence service to use inline content
- ✅ Test with sample repositories

**Day 5**:
- ✅ Integration testing
- ✅ Performance benchmarks
- ✅ Documentation updates

**Deliverable**: Working cloud-native ingestion with inline content (no filesystem mounts required)

### Week 2: Production (Object Storage)

**Days 1-3**:
- Add S3/MinIO client library
- Implement upload logic with presigned URLs
- Add object storage config to event schema

**Days 4-5**:
- Update intelligence service to download from URLs
- Implement local cache for downloaded files
- Security: IAM roles, presigned URLs

**Days 6-7**:
- Integration testing with S3
- Performance benchmarks (upload/download latency)
- Cost monitoring setup

**Deliverable**: Production-ready ingestion supporting large files via S3

### Week 3: Advanced (Git References)

**Days 1-3**:
- Add Git client to intelligence service
- Implement clone caching with LRU eviction
- Add credential management

**Days 4-5**:
- Optimize: shallow clones, sparse checkout
- Test with large repositories
- Delta ingestion workflow

**Days 6-7**:
- Integration testing with Git
- Performance benchmarks (clone times)
- Documentation and examples

**Deliverable**: Full-featured ingestion supporting Git repositories

---

## Success Metrics

### Technical Metrics

**Performance**:
- ✅ Inline content: <50ms average per file
- ✅ S3 content: <400ms average per file
- ✅ Git content (warm): <200ms average per file
- ✅ Batch processing: <95s for 1000 files

**Reliability**:
- ✅ 99.9% success rate for inline content
- ✅ 99.5% success rate for S3 content
- ✅ 99% success rate for Git content (accounting for clone failures)

**Cost**:
- ✅ <$5/month for typical repository (1000 files)
- ✅ S3 storage costs <$1/GB/month
- ✅ Compute costs <$10/month for intelligence service

### Business Metrics

**Adoption**:
- ✅ 100% of new ingestion jobs use v2 schema
- ✅ 80% of files use inline strategy (cost optimization)
- ✅ 20% of files use S3 strategy (large files)
- ✅ <5% of files use Git strategy (continuous ingestion)

**Scalability**:
- ✅ Support 100+ repositories ingested monthly
- ✅ Support repositories up to 10GB size
- ✅ Support batch sizes up to 1000 files
- ✅ Support concurrent ingestion (10+ jobs simultaneously)

---

## Risks & Mitigations

### Risk 1: Kafka Message Size Limits

**Risk**: Inline content may exceed Kafka message size limit (1MB default, 10MB max)

**Mitigation**:
- ✅ Enforce 100KB per-file limit for inline content
- ✅ Enforce 5MB per-batch limit (safety margin)
- ✅ Automatic fallback to S3 for large files
- ✅ Compression (gzip) for large batches

### Risk 2: S3 Costs

**Risk**: Frequent uploads/downloads may incur high S3 costs

**Mitigation**:
- ✅ Use inline for small files (majority of code)
- ✅ Implement aggressive caching (reduce downloads)
- ✅ Set lifecycle policies (auto-delete after N days)
- ✅ Use S3 Intelligent-Tiering (auto cost optimization)
- ✅ Monitor costs with CloudWatch

### Risk 3: Git Clone Performance

**Risk**: Large repository clones may timeout (>60s)

**Mitigation**:
- ✅ Use shallow clones (--depth 1)
- ✅ Use sparse checkout (only needed files)
- ✅ Implement clone caching (LRU eviction)
- ✅ Set timeout limits (5 minutes)
- ✅ Fallback to inline for repeated failures

### Risk 4: Security (Credential Leakage)

**Risk**: Credentials or presigned URLs may be logged/exposed

**Mitigation**:
- ✅ Never log credentials or presigned URLs
- ✅ Use Secret Manager for Git credentials
- ✅ Use IAM roles for S3 access (no credentials)
- ✅ Expire presigned URLs after 24 hours
- ✅ Audit logs for credential access

---

## Conclusion

### Recommended Solution: Hybrid Approach

**Why Hybrid?**
- ✅ **Best of all worlds**: Fast (inline), scalable (S3), version-aware (Git)
- ✅ **Cost-optimized**: Inline for 95% of files, S3 only when needed
- ✅ **Cloud-native**: No filesystem mounts, works everywhere
- ✅ **Backward compatible**: Gradual migration from v1 to v2
- ✅ **Production-ready**: Security, monitoring, fallbacks

### Implementation Priority

**Phase 1 (MVP)**: Inline content support → **2 days** → Enables cloud deployment
**Phase 2 (Production)**: Object storage support → **5 days** → Enables large files
**Phase 3 (Advanced)**: Git references → **7 days** → Enables continuous ingestion

**Total Timeline**: 2-3 weeks for full implementation

### Next Steps

1. **Review this proposal** with team and stakeholders
2. **Prototype Phase 1** (inline content) → Validate approach
3. **Implement Phase 2** (object storage) → Production readiness
4. **Implement Phase 3** (Git) → Advanced features
5. **Monitor & optimize** → Cost, performance, reliability

---

## Appendix A: Code Examples

### Example 1: Inline Content (Phase 1)

**Updated batch_processor.py**:
```python
async def _build_event(
    self,
    correlation_id: str,
    project_name: str,
    project_path: Path,
    files: List[Dict[str, Any]],
    batch_id: int,
) -> Dict[str, Any]:
    """Build INDEX_PROJECT_REQUESTED event with inline content"""

    enriched_files = []
    total_content_size = 0

    for file_dict in files:
        file_path = Path(file_dict["file_path"])
        size_bytes = file_dict["size_bytes"]

        # Strategy: inline for files <100KB
        if size_bytes <= 100_000:
            try:
                content = file_path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(content.encode()).hexdigest()

                enriched_file = {
                    "relative_path": file_dict["relative_path"],
                    "language": file_dict["language"],
                    "size_bytes": size_bytes,
                    "content_strategy": "inline",
                    "content": content,
                    "content_encoding": "utf-8",
                    "checksum": f"sha256:{checksum}",
                }

                enriched_files.append(enriched_file)
                total_content_size += len(content)
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
        else:
            logger.warning(f"File too large for inline: {file_path} ({size_bytes} bytes)")

    # Safety check: enforce batch size limit (5MB)
    if total_content_size > 5_000_000:
        raise ValueError(f"Batch content size exceeds 5MB: {total_content_size} bytes")

    return {
        "event_id": str(uuid4()),
        "event_type": "dev.archon-intelligence.tree.index-project-requested.v2",
        "correlation_id": correlation_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "2.0.0",
        "metadata": {
            "batch_id": batch_id,
            "batch_size": len(enriched_files),
            "content_strategy": "inline",
            "total_content_size_bytes": total_content_size,
        },
        "payload": {
            "project_name": project_name,
            "project_path": None,  # ✅ No local path needed
            "content_strategy": "inline",
            "files": enriched_files,
            "include_tests": True,
            "force_reindex": self.force_reindex,
        },
    }
```

### Example 2: Object Storage (Phase 2)

**New content_storage.py**:
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import boto3
from botocore.config import Config

class ContentStorageClient(ABC):
    """Abstract interface for content storage"""

    @abstractmethod
    async def upload_file(self, file_path: Path, object_key: str) -> str:
        """Upload file and return permanent URL"""
        pass

    @abstractmethod
    async def generate_presigned_url(self, object_key: str, expires_in: int = 86400) -> str:
        """Generate presigned URL for secure access"""
        pass

    @abstractmethod
    async def download_file(self, url: str, dest_path: Path) -> None:
        """Download file from URL"""
        pass


class S3StorageClient(ContentStorageClient):
    """AWS S3 storage client"""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    async def upload_file(self, file_path: Path, object_key: str) -> str:
        """Upload file to S3 and return permanent URL"""
        self.s3_client.upload_file(
            str(file_path),
            self.bucket,
            object_key,
            ExtraArgs={"ServerSideEncryption": "AES256"},
        )
        return f"s3://{self.bucket}/{object_key}"

    async def generate_presigned_url(self, object_key: str, expires_in: int = 86400) -> str:
        """Generate presigned URL (default 24h expiry)"""
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    async def download_file(self, url: str, dest_path: Path) -> None:
        """Download file from presigned URL"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            dest_path.write_bytes(response.content)


class MinIOStorageClient(ContentStorageClient):
    """MinIO storage client (local dev)"""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

    # Same interface as S3StorageClient
    # ...
```

### Example 3: Git Content Fetcher (Phase 3)

**New git_content_fetcher.py**:
```python
import asyncio
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

@dataclass
class GitCredentials:
    """Git credentials for private repositories"""
    type: str  # "token" or "ssh_key"
    value: str  # Token string or SSH key path

class GitContentFetcher:
    """Fetch content from Git repositories with caching"""

    def __init__(self, cache_dir: Path, max_cache_size_gb: int = 50):
        self.cache_dir = cache_dir
        self.max_cache_size_gb = max_cache_size_gb
        self._clone_cache: Dict[str, Path] = {}  # {repo_url:commit_sha: clone_path}

    async def fetch_file_content(
        self,
        git_url: str,
        commit_sha: str,
        file_path: str,
        credentials: Optional[GitCredentials] = None,
    ) -> str:
        """Fetch file content from Git repository"""

        # Check cache first
        cache_key = f"{git_url}:{commit_sha}"
        if cache_key in self._clone_cache:
            clone_path = self._clone_cache[cache_key]
            return (clone_path / file_path).read_text()

        # Clone repository (shallow)
        clone_path = await self._clone_repo(git_url, commit_sha, credentials)
        self._clone_cache[cache_key] = clone_path

        # Read file
        return (clone_path / file_path).read_text()

    async def _clone_repo(
        self,
        git_url: str,
        commit_sha: str,
        credentials: Optional[GitCredentials],
    ) -> Path:
        """Clone repository with shallow depth"""

        clone_dir = self.cache_dir / commit_sha[:8]
        clone_dir.mkdir(parents=True, exist_ok=True)

        # Build git clone command
        cmd = [
            "git", "clone",
            "--depth", "1",
            "--single-branch",
            "--branch", commit_sha,
            git_url,
            str(clone_dir),
        ]

        # Add credentials if provided
        if credentials and credentials.type == "token":
            # Use credential helper for token
            cmd.insert(2, f"-c credential.helper='!f() {{ echo \"username=git\"; echo \"password={credentials.value}\"; }}; f'")

        # Execute git clone
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode()}")

        return clone_dir
```

---

## Appendix B: Configuration Examples

### Phase 1: Inline Content (No Config Required)

```bash
# Environment variables (existing)
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_TOPIC=dev.archon-intelligence.tree.index-project-requested.v2

# Run bulk ingest (content included inline)
python scripts/bulk_ingest_repository.py /path/to/project
```

### Phase 2: Object Storage (S3)

```bash
# Environment variables
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_TOPIC=dev.archon-intelligence.tree.index-project-requested.v2

# Content storage config
CONTENT_STORAGE_PROVIDER=s3
CONTENT_STORAGE_BUCKET=archon-artifacts
CONTENT_STORAGE_REGION=us-east-1
CONTENT_STORAGE_LARGE_FILE_THRESHOLD=102400  # 100KB

# AWS credentials (use IAM role in production)
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>

# Run bulk ingest (large files uploaded to S3)
python scripts/bulk_ingest_repository.py /path/to/project
```

### Phase 3: Git References

```bash
# Environment variables
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_TOPIC=dev.archon-intelligence.tree.index-project-requested.v2

# Git config
CONTENT_STRATEGY=git_reference
GIT_CLONE_CACHE_DIR=/tmp/git-cache
GIT_CLONE_CACHE_MAX_SIZE_GB=50

# Run bulk ingest from Git URL
python scripts/bulk_ingest_repository.py \
  --git-url https://github.com/user/repo.git \
  --git-ref abc123def456... \
  --project-name my-project
```

---

**End of Document**
