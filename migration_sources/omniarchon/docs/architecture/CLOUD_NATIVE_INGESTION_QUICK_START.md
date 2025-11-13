# Cloud-Native Ingestion: Quick Start Guide

**For Full Details**: See [CLOUD_NATIVE_INGESTION_ARCHITECTURE.md](./CLOUD_NATIVE_INGESTION_ARCHITECTURE.md)

---

## Problem Summary

**Current State** ❌
```
Local Machine               Docker Container
┌──────────────┐           ┌─────────────────┐
│ Files at:    │           │ Needs mount at: │
│ /Volumes/... │─────X─────│ /Volumes/...    │
└──────────────┘           └─────────────────┘
    Doesn't work in cloud, CI/CD, or different machines
```

**New State** ✅
```
Any Environment            Docker Container
┌──────────────┐           ┌─────────────────┐
│ Send content │──Kafka───>│ Receives content│
│ inline/S3/Git│           │ directly        │
└──────────────┘           └─────────────────┘
    Works everywhere - no filesystem mounts needed
```

---

## Three Content Strategies

### 1. Inline Content (Small Files)
```
Publisher                Kafka               Consumer
┌─────────┐            ┌───────┐           ┌──────────┐
│ Read    │───────────>│ {     │──────────>│ Use      │
│ file.py │ {content:  │ content│           │ content  │
│ "def.." │  "def..."}│ }     │           │ directly │
└─────────┘            └───────┘           └──────────┘

✅ Fast: 5-50ms
✅ Free: No storage costs
❌ Limit: <100KB per file
```

### 2. Object Storage (Large Files)
```
Publisher                S3                  Consumer
┌─────────┐            ┌──────┐            ┌──────────┐
│ Upload  │───────────>│ Store│            │ Download │
│ file    │ {url: s3://│ file │<───────────│ from URL │
└─────────┘            └──────┘            └──────────┘
     │                                           ▲
     └────────────> Kafka ──────────────────────┘
                  {content_url: "s3://..."}

✅ Scalable: Unlimited file sizes
✅ Cloud-native: Works everywhere
❌ Cost: ~$0.023/GB/month + transfer
```

### 3. Git References (Repositories)
```
Publisher                Kafka               Consumer
┌─────────┐            ┌───────┐           ┌──────────┐
│ Send    │───────────>│ {     │──────────>│ Clone &  │
│ Git URL │ {git_url,  │ git   │           │ read file│
│ + SHA   │  commit}   │ ref}  │           │ from repo│
└─────────┘            └───────┘           └──────────┘

✅ Version control: Built-in
✅ Efficient: Delta updates
❌ Slow: 5-60s cold clone
```

---

## Strategy Decision Tree

```
Start: Need to ingest file
         |
         v
    File size < 100KB?
    /              \
  YES               NO
   |                 |
   v                 v
INLINE          Source = Git?
                /          \
              YES           NO
               |             |
               v             v
          GIT_REF      OBJECT_STORAGE
                           (S3)
```

---

## Implementation Phases

### Phase 1: MVP (2 days) - Inline Content

**Goal**: Enable cloud deployment without filesystem mounts

**Changes**:
1. ✅ Read file content in `bulk_ingest.py`
2. ✅ Include content in Kafka messages
3. ✅ Update event schema to v2.0.0
4. ✅ Use inline content in intelligence service

**Result**: Works in any environment (local, cloud, CI/CD)

**Example**:
```python
# Before (v1) - Requires filesystem mount
{
  "files": [
    {"file_path": "/Volumes/PRO-G40/Code/repo/api.py"}  # ❌
  ]
}

# After (v2) - Content included
{
  "files": [
    {
      "relative_path": "api.py",
      "content_strategy": "inline",
      "content": "def hello():\n    print('hello')\n"  # ✅
    }
  ]
}
```

### Phase 2: Production (5 days) - Object Storage

**Goal**: Support large files (>100KB) via S3/GCS/MinIO

**Changes**:
1. ✅ Add S3 client to `bulk_ingest.py`
2. ✅ Upload large files to S3
3. ✅ Send presigned URLs in Kafka messages
4. ✅ Download from URLs in intelligence service
5. ✅ Add local cache for downloaded files

**Result**: Supports unlimited file sizes, production-ready

### Phase 3: Advanced (7 days) - Git References

**Goal**: Support continuous ingestion from Git repositories

**Changes**:
1. ✅ Add Git client to intelligence service
2. ✅ Implement clone caching
3. ✅ Handle private repos (SSH/tokens)
4. ✅ Optimize with shallow clones

**Result**: Full continuous integration support

---

## Quick Cost Comparison

| Strategy | 1000 Files (25KB avg) | Use When |
|----------|----------------------|----------|
| **Inline** | **$2/month** | Small files, dev |
| **S3** | **$5/month** | Large files, prod |
| **Git** | **$5/month** | Continuous ingestion |

**Real Example** (Omniarchon repo):
- 1000 files, 95% <100KB
- Strategy: Inline (95%) + S3 (5%)
- **Cost: ~$2/month** 💰

---

## Quick Performance Comparison

| Strategy | Latency | Throughput |
|----------|---------|------------|
| **Inline** | **5-50ms** | **500-2000 files/sec** |
| **S3** | 100-400ms | 50-200 files/sec |
| **Git** (warm) | 50-200ms | 50-200 files/sec |
| **Git** (cold) | 5-60s | 1-10 files/sec |

**Recommendation**: Use inline for 95% of files (fast + free)

---

## Migration Path

### Step 1: Update Event Schema (v1.0.0 → v2.0.0)

**v1.0.0 (Current)** - Requires filesystem:
```json
{
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v1",
  "payload": {
    "project_name": "omniarchon",
    "project_path": "/Volumes/PRO-G40/Code/omniarchon",
    "files": [
      {
        "file_path": "/Volumes/.../api.py",
        "relative_path": "api.py",
        "size_bytes": 15234
      }
    ]
  }
}
```

**Problems with v1.0.0**:
- ❌ No `schema_version` field
- ❌ No inline content - requires filesystem mount
- ❌ No content verification (checksum)
- ❌ Environment-specific paths

**v2.0.0 (Phase 1)** - Cloud-native:
```json
{
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v2",
  "schema_version": "2.0.0",
  "payload": {
    "project_name": "omniarchon",
    "project_path": null,
    "content_strategy": "inline",
    "files": [
      {
        "relative_path": "api.py",
        "absolute_path": "/Volumes/.../api.py",
        "content": "def hello(): return 'world'",
        "content_strategy": "inline",
        "content_encoding": "utf-8",
        "checksum": "sha256:abc123...",
        "size_bytes": 15234
      }
    ]
  }
}
```

**Improvements in v2.0.0**:
- ✅ `schema_version` field for versioning
- ✅ `content` field with inline content
- ✅ `content_strategy` enum ("inline", "object_storage", "git_reference")
- ✅ `checksum` for content verification (SHA256/BLAKE3)
- ✅ `project_path` is null (no filesystem dependency)
- ✅ Works in any environment (cloud, CI/CD, local)

### Step 2: Update Intelligence Service

**Add fallback logic** (supports v1 + v2):
```python
async def _get_file_content(self, request):
    # Priority 1: Inline content (v2)
    if request.content:
        return request.content

    # Priority 2: Object storage (v2)
    if request.content_url:
        return await download_from_url(request.content_url)

    # Priority 3: Git reference (v2)
    if request.git_url:
        return await clone_and_read(request.git_url, request.file_path)

    # Priority 4: Local file (v1 fallback)
    if request.file_path:
        return Path(request.file_path).read_text()  # ❌ Requires mount
```

### Step 3: Gradual Rollout

**Week 1**: Deploy v2-compatible intelligence service (supports v1 + v2)
**Week 2**: Update `bulk_ingest.py` to send v2 messages (inline content)
**Week 3**: Test in cloud (no filesystem mounts)
**Week 4**: Remove v1 fallback code

---

## Testing Checklist

### Phase 1: Inline Content
- [ ] Small files (<100KB) included inline
- [ ] Event schema v2.0.0 validation
- [ ] Intelligence service uses inline content
- [ ] No filesystem access required
- [ ] Works in Docker without mounts
- [ ] Performance: <50ms per file

### Phase 2: Object Storage
- [ ] Large files (>100KB) uploaded to S3
- [ ] Presigned URLs generated (24h expiry)
- [ ] Intelligence service downloads from URLs
- [ ] Local cache for downloaded files
- [ ] Handles S3 failures gracefully
- [ ] Performance: <400ms per file

### Phase 3: Git References
- [ ] Clone from Git URL + commit SHA
- [ ] Cache clones (LRU eviction)
- [ ] Handle private repos (SSH/token)
- [ ] Shallow clones (--depth 1)
- [ ] Performance: <200ms (warm cache)

---

## Success Criteria

**Phase 1 Complete When**:
- ✅ Can ingest repository in Docker container **without** volume mounts
- ✅ All files <100KB processed successfully
- ✅ Performance: <95s for 1000 files
- ✅ Event schema v2.0.0 published to Kafka

**Phase 2 Complete When**:
- ✅ Can ingest files >100KB via S3
- ✅ Presigned URLs expire after 24h
- ✅ Local cache reduces download latency
- ✅ Cost: <$5/month for typical repo

**Phase 3 Complete When**:
- ✅ Can ingest from Git URL (public + private)
- ✅ Clone cache speeds up repeated ingestion
- ✅ Shallow clones reduce clone time
- ✅ Performance: <200ms per file (warm cache)

---

## Common Issues & Solutions

### Issue 1: Kafka Message Too Large

**Symptom**: `MessageSizeTooLargeError` when publishing batch

**Solution**:
```python
# Enforce 100KB per-file limit
if file_size > 100_000:
    # Upload to S3 instead of inline
    content_url = await storage.upload_file(file_path)
    file_dict["content_strategy"] = "object_storage"
    file_dict["content_url"] = content_url
```

### Issue 2: S3 Download Timeout

**Symptom**: Timeout when downloading large files from S3

**Solution**:
```python
# Increase download timeout
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.get(presigned_url)
```

### Issue 3: Git Clone Slow

**Symptom**: Git clone takes >60s for large repositories

**Solution**:
```bash
# Use shallow clone with depth 1
git clone --depth 1 --single-branch <url>

# Or use sparse checkout (only needed files)
git sparse-checkout set src/api.py
```

---

## Next Steps

1. **Review** full architecture document: [CLOUD_NATIVE_INGESTION_ARCHITECTURE.md](./CLOUD_NATIVE_INGESTION_ARCHITECTURE.md)
2. **Prototype** Phase 1 (inline content): 2 days
3. **Test** with sample repository in Docker (no mounts)
4. **Implement** Phase 2 (S3) if needed: 5 days
5. **Deploy** to production environment

---

**Questions?** See full architecture document for detailed designs, code examples, and cost analysis.
