# Cloud-Native Ingestion: Implementation Checklist

**Status**: Planning
**Start Date**: TBD
**Target Completion**: TBD

---

## Phase 1: MVP - Inline Content (2 Days)

**Goal**: Enable cloud deployment without filesystem mounts

### Day 1: Event Schema & Publisher Updates

**Morning** (4 hours):
- [ ] Update event schema to v2.0.0
  - [ ] Create `ModelEventIndexProjectRequestedV2` in `models/`
  - [ ] Add `content_strategy` enum: `inline`, `object_storage`, `git_reference`
  - [ ] Add file fields: `content`, `content_encoding`, `checksum`
  - [ ] Document schema changes in `docs/events/`
- [ ] Update `batch_processor.py`
  - [ ] Add `_read_file_content(file_path)` helper method
  - [ ] Add `_calculate_checksum(content)` helper method (SHA256)
  - [ ] Update `_build_event()` to include file content inline
  - [ ] Add content size validation (100KB per file, 5MB per batch)
  - [ ] Add error handling for unreadable files

**Afternoon** (4 hours):
- [ ] Update `bulk_ingest_repository.py`
  - [ ] Add `--content-strategy` CLI argument (default: `auto`)
  - [ ] Add `--inline-size-limit` CLI argument (default: 100KB)
  - [ ] Update batch processing to use new event schema
  - [ ] Add progress reporting for content reading
- [ ] Write unit tests for `batch_processor.py`
  - [ ] Test file content reading (UTF-8, Latin-1, binary)
  - [ ] Test checksum calculation
  - [ ] Test size limit enforcement
  - [ ] Test batch size limit enforcement
  - [ ] Test error handling (missing files, unreadable files)

**End of Day 1 Deliverables**:
- ✅ Event schema v2.0.0 defined and documented
- ✅ Publisher includes file content inline
- ✅ Unit tests passing (>90% coverage)

### Day 2: Consumer Updates & Integration Testing

**Morning** (4 hours):
- [ ] Update `BridgeIntelligenceRequest` model
  - [ ] Add `content: Optional[str]` field
  - [ ] Add `content_strategy: Optional[str]` field
  - [ ] Add `checksum: Optional[str]` field
  - [ ] Update validation logic
- [ ] Update `bridge_intelligence_generator.py`
  - [ ] Prioritize `request.content` over `file_path`
  - [ ] Add checksum verification (optional but recommended)
  - [ ] Add logging for content source used
  - [ ] Maintain backward compatibility (v1 fallback)

**Afternoon** (4 hours):
- [ ] Integration testing
  - [ ] Test end-to-end: ingest → Kafka → intelligence service
  - [ ] Test small repository (100 files, all <100KB)
  - [ ] Test mixed sizes (some files >100KB, should warn/skip)
  - [ ] Test in Docker container **without** volume mounts
  - [ ] Test error recovery (unreadable files)
- [ ] Performance benchmarking
  - [ ] Measure batch processing time (target: <95s for 1000 files)
  - [ ] Measure intelligence generation time (target: <2000ms)
  - [ ] Measure Kafka message sizes (should be <5MB per batch)
  - [ ] Document results in `docs/performance/`

**End of Day 2 Deliverables**:
- ✅ Intelligence service uses inline content
- ✅ End-to-end integration tests passing
- ✅ Performance benchmarks documented
- ✅ Works in Docker without volume mounts

---

## Phase 2: Production - Object Storage (5 Days)

**Goal**: Support large files (>100KB) via S3/GCS/MinIO

### Day 1: Storage Client Library

- [ ] Create `scripts/lib/content_storage.py`
  - [ ] Define `ContentStorageClient` abstract base class
  - [ ] Implement `S3StorageClient` (AWS S3)
  - [ ] Implement `MinIOStorageClient` (local dev)
  - [ ] Add `upload_file(file_path, object_key)` method
  - [ ] Add `generate_presigned_url(object_key, expires_in)` method
  - [ ] Add error handling and retries
- [ ] Write unit tests for storage clients
  - [ ] Test S3 upload/download (mocked)
  - [ ] Test presigned URL generation
  - [ ] Test error handling (network failures)

### Day 2: Publisher Integration

- [ ] Update `batch_processor.py`
  - [ ] Add `storage_client: Optional[ContentStorageClient]` parameter
  - [ ] Update `_build_event()` to use storage for large files
  - [ ] Generate object keys: `projects/{project_name}/{checksum}.{ext}`
  - [ ] Upload large files (>100KB) to storage
  - [ ] Generate presigned URLs (24h expiry)
  - [ ] Add `content_url` and `content_url_type` to file dict
- [ ] Update `bulk_ingest_repository.py`
  - [ ] Add `--storage-provider` CLI argument (s3, minio, none)
  - [ ] Add `--storage-bucket` CLI argument
  - [ ] Initialize storage client based on config
  - [ ] Pass storage client to batch processor

### Day 3: Consumer Integration

- [ ] Update `bridge_intelligence_generator.py`
  - [ ] Add `_download_from_url(url)` method
  - [ ] Add local cache for downloaded files (`/tmp/archon-cache/`)
  - [ ] Update `_get_file_content()` to handle `content_url`
  - [ ] Add LRU cache eviction (max 10GB cache size)
  - [ ] Add checksum verification after download
- [ ] Add timeout and retry logic
  - [ ] Timeout: 60s for download
  - [ ] Retries: 3 attempts with exponential backoff

### Day 4: Configuration & Security

- [ ] Add environment variables
  - [ ] `CONTENT_STORAGE_PROVIDER` (s3, minio)
  - [ ] `CONTENT_STORAGE_BUCKET`
  - [ ] `CONTENT_STORAGE_REGION`
  - [ ] `CONTENT_STORAGE_ENDPOINT` (for MinIO)
  - [ ] `CONTENT_CACHE_DIR` (default: `/tmp/archon-cache/`)
  - [ ] `CONTENT_CACHE_MAX_SIZE_GB` (default: 10)
- [ ] Document security best practices
  - [ ] Use IAM roles (no hardcoded credentials)
  - [ ] Use presigned URLs (time-limited access)
  - [ ] Set S3 bucket policies (no public access)
  - [ ] Enable S3 server-side encryption (AES256)

### Day 5: Testing & Documentation

- [ ] Integration testing
  - [ ] Test large files (>100KB) uploaded to S3
  - [ ] Test presigned URL generation and expiry
  - [ ] Test intelligence service downloads from S3
  - [ ] Test local cache hit/miss scenarios
  - [ ] Test S3 failure scenarios (network issues)
- [ ] Performance benchmarking
  - [ ] Measure upload latency (target: <200ms)
  - [ ] Measure download latency (target: <200ms)
  - [ ] Measure cache hit rate (target: >60%)
- [ ] Documentation
  - [ ] Update README with S3 setup instructions
  - [ ] Document cost estimates ($0.023/GB/month)
  - [ ] Add example configurations (S3, MinIO)

**End of Phase 2 Deliverables**:
- ✅ Large files (>100KB) supported via S3
- ✅ Presigned URLs for secure access
- ✅ Local cache reduces download latency
- ✅ Production-ready with IAM roles

---

## Phase 3: Advanced - Git References (7 Days)

**Goal**: Support continuous ingestion from Git repositories

### Day 1-2: Git Client Implementation

- [ ] Create `services/intelligence/src/services/git_content_fetcher.py`
  - [ ] Define `GitContentFetcher` class
  - [ ] Implement `fetch_file_content(git_url, commit_sha, file_path)` method
  - [ ] Add clone caching with LRU eviction
  - [ ] Cache directory: `/tmp/git-cache/{commit_sha}/`
  - [ ] Max cache size: 50GB
- [ ] Implement Git operations
  - [ ] Shallow clone: `git clone --depth 1 --branch <commit>`
  - [ ] Sparse checkout: Only clone needed files
  - [ ] Checkout specific commit: `git checkout <commit_sha>`

### Day 3: Credential Management

- [ ] Add credential support
  - [ ] Define `GitCredentials` dataclass (type, value)
  - [ ] Support token authentication (HTTPS)
  - [ ] Support SSH key authentication
  - [ ] Integrate with Secret Manager (AWS Secrets Manager)
- [ ] Update event schema
  - [ ] Add `git_url`, `git_ref`, `git_branch` to payload
  - [ ] Add `git_credentials` with secret reference
  - [ ] Document credential security model

### Day 4: Publisher Integration

- [ ] Update `bulk_ingest_repository.py`
  - [ ] Add `--git-url` CLI argument
  - [ ] Add `--git-ref` CLI argument (commit SHA or branch)
  - [ ] Add `--git-credentials-path` CLI argument (optional)
  - [ ] Update `_build_event()` to use `git_reference` strategy
  - [ ] Skip file reading (files fetched by consumer)

### Day 5: Consumer Integration

- [ ] Update `bridge_intelligence_generator.py`
  - [ ] Initialize `GitContentFetcher` on startup
  - [ ] Update `_get_file_content()` to handle Git references
  - [ ] Add `_fetch_from_git(git_url, git_ref, file_path)` method
  - [ ] Add cache warming (preload frequently used repos)

### Day 6: Optimization

- [ ] Performance tuning
  - [ ] Benchmark clone times (small/medium/large repos)
  - [ ] Implement parallel file fetching (10 concurrent)
  - [ ] Add clone timeout (5 minutes)
  - [ ] Add fallback to inline for repeated failures
- [ ] Cache management
  - [ ] Implement LRU eviction policy
  - [ ] Add cache metrics (hit rate, size, evictions)
  - [ ] Add cache warming API endpoint

### Day 7: Testing & Documentation

- [ ] Integration testing
  - [ ] Test public repository ingestion
  - [ ] Test private repository ingestion (SSH/token)
  - [ ] Test large repository (>1GB)
  - [ ] Test clone cache hit/miss scenarios
  - [ ] Test credential handling (no leakage)
- [ ] Performance benchmarking
  - [ ] Measure cold clone time (target: <60s for typical repo)
  - [ ] Measure warm cache hit time (target: <200ms)
  - [ ] Measure cache eviction overhead
- [ ] Documentation
  - [ ] Update README with Git ingestion instructions
  - [ ] Document credential setup (SSH keys, tokens)
  - [ ] Add example Git ingestion workflows

**End of Phase 3 Deliverables**:
- ✅ Git repositories supported (public + private)
- ✅ Clone caching reduces latency
- ✅ Secure credential management
- ✅ Performance: <200ms (warm cache)

---

## Phase 4: Optimization & Monitoring (2-3 Days)

**Goal**: Production readiness with monitoring and cost optimization

### Day 1: Metrics & Monitoring

- [ ] Add Prometheus metrics
  - [ ] `archon_ingestion_files_total` (counter, by content_strategy)
  - [ ] `archon_ingestion_bytes_total` (counter, by content_strategy)
  - [ ] `archon_ingestion_duration_seconds` (histogram, by content_strategy)
  - [ ] `archon_storage_upload_duration_seconds` (histogram)
  - [ ] `archon_storage_download_duration_seconds` (histogram)
  - [ ] `archon_git_clone_duration_seconds` (histogram)
  - [ ] `archon_cache_hit_rate` (gauge, by cache_type)
  - [ ] `archon_cache_size_bytes` (gauge, by cache_type)
- [ ] Add health checks
  - [ ] Storage backend connectivity (S3/MinIO)
  - [ ] Git client availability
  - [ ] Cache disk space usage

### Day 2: Cost Monitoring

- [ ] Add cost tracking
  - [ ] S3 storage cost estimation (bytes * $0.023/GB/month)
  - [ ] S3 transfer cost estimation (bytes * $0.09/GB)
  - [ ] Compute cost estimation (CPU time * rate)
  - [ ] Total cost per ingestion job
- [ ] Create cost dashboard
  - [ ] Grafana dashboard for cost metrics
  - [ ] Alerts for cost anomalies (>$10/day)
  - [ ] Cost attribution by project

### Day 3: Automatic Strategy Selection

- [ ] Implement intelligent strategy selector
  - [ ] ML model to predict optimal strategy
  - [ ] Features: file_size, language, source, history
  - [ ] Training data: historical ingestion metrics
  - [ ] Fallback: Rule-based selector (current logic)
- [ ] Add fallback logic
  - [ ] S3 failure → Inline (if small enough)
  - [ ] Git failure → Inline (if files available locally)
  - [ ] Inline too large → S3 (automatic upgrade)

---

## Testing Matrix

### Unit Tests
| Component | Coverage Target | Status |
|-----------|-----------------|--------|
| `batch_processor.py` | >90% | ⏳ TODO |
| `content_storage.py` | >85% | ⏳ TODO |
| `git_content_fetcher.py` | >80% | ⏳ TODO |
| `bridge_intelligence_generator.py` | >90% | ⏳ TODO |

### Integration Tests
| Scenario | Status |
|----------|--------|
| Small repo (100 files, all inline) | ⏳ TODO |
| Large repo (1000 files, mixed strategies) | ⏳ TODO |
| Git ingestion (public repo) | ⏳ TODO |
| Git ingestion (private repo) | ⏳ TODO |
| S3 large file upload/download | ⏳ TODO |
| Cache hit scenarios | ⏳ TODO |
| Error recovery scenarios | ⏳ TODO |

### Performance Tests
| Metric | Target | Status |
|--------|--------|--------|
| Inline content per file | <50ms | ⏳ TODO |
| S3 upload per file | <200ms | ⏳ TODO |
| S3 download per file | <200ms | ⏳ TODO |
| Git clone (cold) | <60s | ⏳ TODO |
| Git file fetch (warm) | <200ms | ⏳ TODO |
| Batch processing (1000 files) | <95s | ⏳ TODO |

---

## Acceptance Criteria

### Phase 1: Inline Content
- [ ] Can ingest repository in Docker **without** volume mounts
- [ ] All files <100KB processed successfully with inline content
- [ ] Performance: <95s for 1000 files (inline strategy)
- [ ] Event schema v2.0.0 validates successfully
- [ ] Backward compatible with v1 event schema

### Phase 2: Object Storage
- [ ] Can ingest files >100KB via S3/MinIO
- [ ] Presigned URLs generated with 24h expiry
- [ ] Local cache reduces download latency by >60%
- [ ] Handles S3 failures gracefully (retries, fallback)
- [ ] Cost: <$5/month for typical repository (1000 files)

### Phase 3: Git References
- [ ] Can ingest from Git URL (public + private repos)
- [ ] Clone cache speeds up repeated ingestion (>60% hit rate)
- [ ] Shallow clones reduce clone time (<60s for typical repo)
- [ ] Performance: <200ms per file (warm cache)
- [ ] Secure credential management (no leakage in logs/Kafka)

### Phase 4: Production Ready
- [ ] Prometheus metrics exported and scraping
- [ ] Cost monitoring dashboard functional
- [ ] Automatic strategy selection working
- [ ] Health checks passing (storage, Git, cache)
- [ ] Documentation complete and reviewed

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Status |
|------|------------|--------|------------|--------|
| Kafka message size limits | High | High | Enforce 100KB per-file limit, use S3 fallback | ⏳ Planned |
| S3 costs exceed budget | Medium | Medium | Monitor costs, optimize with inline strategy | ⏳ Planned |
| Git clone timeouts | Medium | High | Use shallow clones, implement caching | ⏳ Planned |
| Credential leakage | Low | Critical | Use Secret Manager, no logging of credentials | ⏳ Planned |
| Cache disk space exhaustion | Low | Medium | Implement LRU eviction, monitor disk usage | ⏳ Planned |

---

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing (>85% coverage)
- [ ] All integration tests passing
- [ ] Performance benchmarks meet targets
- [ ] Security review completed
- [ ] Documentation reviewed and approved
- [ ] Backward compatibility verified

### Deployment
- [ ] Deploy v2-compatible intelligence service (supports v1 + v2)
- [ ] Monitor Kafka consumer lag (should remain <1s)
- [ ] Monitor error rates (should be <1%)
- [ ] Verify S3 connectivity and permissions
- [ ] Test end-to-end in staging environment

### Post-Deployment
- [ ] Monitor metrics for 24 hours
- [ ] Verify cost tracking is accurate
- [ ] Check cache hit rates (target: >60%)
- [ ] Update documentation with lessons learned
- [ ] Schedule deprecation of v1 event schema (after 30 days)

---

## Notes & Decisions

### Decision Log

**Decision 1**: Use hybrid approach (inline + S3 + Git)
- **Date**: 2025-10-28
- **Rationale**: Best balance of cost, performance, and flexibility
- **Alternatives considered**: Inline-only (limited scalability), S3-only (higher cost)

**Decision 2**: 100KB threshold for inline content
- **Date**: 2025-10-28
- **Rationale**: 95% of code files are <100KB, stays well under Kafka limits
- **Alternatives considered**: 50KB (too conservative), 1MB (risks Kafka limits)

**Decision 3**: 24h presigned URL expiry
- **Date**: 2025-10-28
- **Rationale**: Balance between security and usability
- **Alternatives considered**: 1h (too short), 7d (security risk)

### Open Questions

1. **S3 Lifecycle Policies**: How long should we retain uploaded files?
   - **Proposal**: 30 days, then auto-delete (can regenerate from source)
   - **Status**: ⏳ Pending decision

2. **Git Cache Size Limits**: What's the right balance?
   - **Proposal**: 50GB max, LRU eviction
   - **Status**: ⏳ Pending decision

3. **Cost Alerts**: What threshold should trigger alerts?
   - **Proposal**: Alert if daily cost exceeds $10
   - **Status**: ⏳ Pending decision

---

## Progress Tracking

**Overall Progress**: 0% (Not Started)

**Phase 1**: 0% (Not Started)
**Phase 2**: 0% (Not Started)
**Phase 3**: 0% (Not Started)
**Phase 4**: 0% (Not Started)

**Last Updated**: 2025-10-28
**Next Review**: TBD

---

**For Questions**: Contact architecture team or see full documentation in [CLOUD_NATIVE_INGESTION_ARCHITECTURE.md](./CLOUD_NATIVE_INGESTION_ARCHITECTURE.md)
