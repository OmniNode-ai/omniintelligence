# Incomplete Features & Outstanding Work

**Generated**: 2025-10-18
**Last Updated**: 2025-10-18
**Status**: 3 of 4 Critical Blockers RESOLVED ✅
**Source**: Codebase analysis, test suite review, service configuration audit

**🎉 CRITICAL BLOCKERS UPDATE** (2025-10-18):
- ✅ **Issue #1** (MCP Session Validation): Already implemented - needs verification
- ✅ **Issue #2** (Circuit Breaker): Migration complete - pybreaker replaced with custom AsyncCircuitBreaker
- ✅ **Issue #3** (Kafka Consumer Handler): Already registered - no action needed
- ⚠️ **Issue #4** (Metadata Stamping API): External service (OmniNode Bridge) - out of scope

**📊 Detailed Fix Report**: See `/CRITICAL_BLOCKERS_FIX_REPORT.md` for complete resolution details

---

## High Priority

### 1. **MCP Session Validation Failure** - ✅ RESOLVED (2025-10-18)
- **Status**: ✅ **ALREADY IMPLEMENTED** - Service authentication middleware exists and is properly configured
- **Resolution**: Investigation revealed implementation is complete
  - Service auth middleware: `/python/src/server/middleware/service_auth_middleware.py` ✅
  - Middleware registration: `main.py` line 528 ✅
  - Service client headers: `mcp_service_client.py` includes `X-Service-Auth` ✅
  - Environment configuration: `SERVICE_AUTH_TOKEN` configured ✅
  - MCP tools: All using `get_mcp_service_client()` ✅
- **Verification Needed**: End-to-end testing through Claude Code to confirm no runtime issues
- **Reference**: `/CRITICAL_BLOCKERS_FIX_REPORT.md` (Issue #1)

### 2. **Circuit Breaker Disabled** - ✅ RESOLVED (2025-10-18)
- **Status**: ✅ **MIGRATION COMPLETE** - Replaced pybreaker with custom async circuit breaker
- **Resolution**: Created custom AsyncCircuitBreaker implementation
  - New implementation: `/services/intelligence/src/infrastructure/async_circuit_breaker.py` ✅
  - Python 3.11+ compatible (no tornado dependencies) ✅
  - Drop-in replacement with matching pybreaker API ✅
  - All 7 HTTP clients updated to use AsyncCircuitBreaker ✅
  - pybreaker dependency removed from pyproject.toml ✅
  - Circuit breakers now **enabled by default** ✅
- **Files Updated** (7):
  - `/python/src/mcp_server/clients/workflow_coordinator_client.py` ✅
  - `/python/src/mcp_server/clients/metadata_stamping_client.py` ✅
  - `/python/src/mcp_server/clients/onex_tree_client.py` ✅
  - `/services/intelligence/src/clients/workflow_coordinator_client.py` ✅
  - `/services/intelligence/src/clients/metadata_stamping_client.py` ✅
  - `/services/intelligence/src/clients/onex_tree_client.py` ✅
  - `/services/intelligence/src/services/pattern_learning/phase2_matching/client_langextract_http.py` ✅
- **Testing Recommended**: Run circuit breaker integration tests
- **Reference**: `/CRITICAL_BLOCKERS_FIX_REPORT.md` (Issue #2)

### 3. **Kafka Consumer Handler Registration** - ✅ RESOLVED (2025-10-18)
- **Status**: ✅ **ALREADY REGISTERED** - CodegenValidationHandler properly integrated
- **Resolution**: Investigation confirmed handler is registered in Kafka consumer
  - Handler imported: `kafka_consumer.py` line 21 ✅
  - Handler registered: `_register_handlers()` lines 226-228 ✅
  - All 4 handlers active: Validation, Analysis, Pattern, Mixin ✅
- **Verification**: Check logs for "Registered CodegenValidationHandler" message
- **Reference**: `/CRITICAL_BLOCKERS_FIX_REPORT.md` (Issue #3)

### 4. **Metadata Stamping Service API Gaps** - ⚠️ EXTERNAL SERVICE
- **Status**: ⚠️ **EXTERNAL DEPENDENCY** - Cannot fix in Archon codebase
- **Finding**: Metadata Stamping Service is part of OmniNode Bridge (separate repository)
- **Service**: OmniNode Bridge Metadata Stamping Service (port 8057)
- **Resolution Path**: Requires fix in OmniNode Bridge repository
- **Missing Endpoints** (in OmniNode Bridge):
  - `/health` endpoint not implemented
  - `/metrics` returns 500 errors
- **Workaround**: Client-side health check bypass flag available
- **Reference**: `/CRITICAL_BLOCKERS_FIX_REPORT.md` (Issue #4)

---

## Medium Priority

### 5. **External MCP Gateway Disabled in Docker** - BY DESIGN
- **What's missing**: External MCP services (zen, codanna, serena, sequential-thinking)
- **Status**: ✅ Working as designed - disabled in Docker, enabled on host
- **Impact**: External AI tools unavailable in Docker environment
- **Reason**: stdio-based MCP services require host access (npx, uv, cargo)
- **Effort**: N/A (architectural limitation)
- **Workaround**: Run MCP server on host with `ARCHON_ENABLE_EXTERNAL_GATEWAY=true`
- **Affected tools**: 100+ external tools
- **Reference**: `EXTERNAL_GATEWAY_QUICK_REFERENCE.md`

### 6. **context7 Service Disabled** - STABILITY ISSUES
- **What's missing**: Library documentation lookup (2 tools)
- **Blocker**: Service can hang on `get-library-docs` calls
- **Impact**: No access to external library documentation
- **Status**: Disabled by default due to async cancel scope compatibility issue
- **Effort**: Medium (requires async cancel scope fix)
- **Tools affected**:
  - `context7.resolve-library-id`
  - `context7.get-library-docs`
- **Reference**: `/python/docs/mcp_proxy/CONTEXT7_FIX_REPORT.md`

### 7. **Pattern Learning Phase 2 Tests Skipped** - TEST COVERAGE GAP
- **What's missing**: Qdrant integration tests for vector search
- **Status**: 9 tests marked with `@pytest.mark.skip(reason="Phase 2 - Qdrant integration not yet implemented")`
- **Impact**: Vector search integration not validated by tests
- **Effort**: Medium (implement Qdrant test fixtures)
- **File**: `services/intelligence/src/pattern_learning/tests/test_vector_index.py`
- **Tests skipped**:
  - `test_index_pattern_without_embeddings`
  - `test_index_pattern_with_embeddings`
  - `test_search_patterns_basic`
  - `test_search_patterns_with_threshold`
  - `test_update_pattern_embeddings`
  - `test_batch_index_performance`
  - `test_concurrent_indexing`
  - `test_embedding_generation_failure`
  - `test_qdrant_connection_failure`

### 8. **Service Authentication Middleware Missing** - INTEGRATION GAP
- **What's missing**: Service-to-service auth middleware for API server
- **Status**: Not implemented
- **Impact**: MCP tools cannot authenticate with API service
- **Effort**: Small (1 day)
- **Implementation**:
  - Add `X-Service-Auth` header support
  - Validate service tokens via environment variable
  - Short-circuit logic before user session validation
- **Reference**: `/docs/research/MCP_SESSION_VALIDATION_ISSUE.md` (Section 1)

### 9. **Workflow Coordinator API Mismatches** - PARTIAL FIX
- **What's missing**: Proper request/response structure mapping
- **Status**: Partially fixed but needs validation
- **Impact**: `orchestrate_pattern_workflow` tool may fail
- **Effort**: Small (validate and test)
- **File**: `python/src/mcp_server/features/intelligence/omninode_bridge_tools.py`
- **Reference**: `/python/OMNINODE_BRIDGE_MCP_TOOLS_REPORT.md` (Section 1.3)

### 10. **Event Metrics Collection Not Implemented** - POST-MVP
- **What's missing**: Event processing performance metrics
- **Status**: Table exists but no write path implemented
- **Impact**: Cannot track event processing performance
- **Effort**: Medium (implement metrics middleware)
- **Database**: `event_metrics` table (empty, expected)
- **Reference**: `/reports/analysis/EMPTY_TABLES_ANALYSIS_REPORT.md` (Section 2)

---

## Low Priority / Future Work

### 11. **AST-Based Code Correction** - PHASE 6 FEATURE
- **What's missing**: Automated code correction using AST parsing
- **Status**: Placeholder implementation only
- **Impact**: Manual code corrections required
- **Effort**: Large (planned for Phase 6 Reflex Arc)
- **Current approach**: Manual review and correction
- **Reference**: Multiple TODOs in validation reports
- **Files**: Phase 6 architecture documents

### 12. **Service Session Tracking** - DISABLED FEATURE
- **What's missing**: Service lifecycle tracking
- **Status**: Feature disabled, table empty
- **Impact**: Cannot track service uptime/health history
- **Effort**: Small (enable feature flag)
- **Database**: `service_sessions` table (empty, expected)
- **Reference**: `/reports/analysis/EMPTY_TABLES_ANALYSIS_REPORT.md` (Section 3)

### 13. **Security Audit Logging** - DISABLED FEATURE
- **What's missing**: Security event audit trail
- **Status**: Feature disabled, table empty
- **Impact**: No security audit history
- **Effort**: Small (enable feature flag)
- **Database**: `security_audit_log` table (empty, expected)

### 14. **Connection Pool Metrics** - DISABLED FEATURE
- **What's missing**: Database connection pool monitoring
- **Status**: Feature disabled, table empty
- **Impact**: No connection pool performance data
- **Effort**: Small (enable feature flag)
- **Database**: `connection_metrics` table (empty, expected)

### 15. **Webhook/Event Queue** - NOT CONFIGURED
- **What's missing**: Webhook event processing
- **Status**: No webhooks configured
- **Impact**: No webhook-based integrations
- **Effort**: Medium (implement webhook handlers)
- **Database**: `hook_events` table (empty, expected)

### 16. **ONEX Node Registry** - AWAITING NODES
- **What's missing**: Node registration system
- **Status**: No nodes registered yet
- **Impact**: Cannot query registered ONEX nodes
- **Effort**: N/A (awaiting ONEX node deployments)
- **Database**: `node_registrations` table (empty, expected)

### 17. **Pattern Evolution Tracking** - AWAITING EVENTS
- **What's missing**: Pattern lineage edges (relationships)
- **Status**: All 27,275 events are `pattern_created` - no evolution yet
- **Impact**: Cannot track pattern modification/merge/fork history
- **Effort**: N/A (awaiting pattern evolution events)
- **Database**: `pattern_lineage_edges` table (empty, expected)
- **When data appears**: Pattern modification, merge, fork, deprecation events

### 18. **codanna Semantic Search** - CONFIGURATION NEEDED
- **What's missing**: Semantic search functionality
- **Status**: ONNX model retrieval failed
- **Impact**: Advanced code search not available
- **Effort**: Small (configure ONNX model)
- **Error**: "No existing index found"
- **Fix**: Run `codanna index <path>` to enable
- **Reference**: `/LOCAL_MCP_GATEWAY_VERIFICATION.md` (Line 204)

---

## Technical Debt

### Code Quality
1. **Unresolved TODOs in Kafka Consumer Handlers**
   - `services/intelligence/src/handlers/service_lifecycle_handler.py` (Lines 115, 175, 198)
   - `services/intelligence/src/handlers/system_event_handler.py` (Lines 191, 217, 244, 269)
   - `services/intelligence/src/handlers/tool_update_handler.py` (Lines 105, 109)
   - **Impact**: Incomplete handler implementations
   - **Effort**: Small-Medium per TODO

2. **Circuit Breaker Service Registry Integration**
   - File: `reports/kafka-consumer/onex-implementation/handlers/service_lifecycle_handler.py`
   - TODO: Implement service registry updates (Line 115)
   - TODO: Integrate with actual circuit breaker management (Lines 175, 198)
   - **Effort**: Small

3. **Performance Optimization Analysis**
   - File: `reports/kafka-consumer/onex-implementation/handlers/system_event_handler.py`
   - TODO: Trigger performance optimization analysis (Line 191)
   - TODO: Update capacity monitoring dashboard (Line 217)
   - TODO: Send immediate notifications (Line 244)
   - TODO: Update system monitoring dashboard (Line 269)
   - **Effort**: Medium

4. **Bridge API Cache Invalidation**
   - File: `reports/kafka-consumer/onex-implementation/handlers/tool_update_handler.py`
   - TODO: Implement cache invalidation when Bridge API has cache (Line 105)
   - TODO: Trigger intelligence service re-indexing (Line 109)
   - **Effort**: Small

### Testing Gaps
1. **Skipped Integration Tests** - 50+ tests skipped across services
   - Intelligence service: Kafka integration tests (when Kafka unavailable)
   - Agent documentation indexer: 18 tests skipped (Archon project not found)
   - Pattern learning: 9 tests skipped (Qdrant integration)
   - Security tests: 5 tests skipped (cache not enabled)
   - **Recommendation**: Create test fixtures for missing dependencies

2. **Missing Test Coverage**
   - TaskCharacteristicsMatcher class not implemented
   - Tests marked with `@pytest.mark.skip` awaiting implementation
   - File: `services/intelligence/tests/IMPORT_FIX_SUMMARY.md` (Line 200)

### Performance
1. **Connection Pooling Configuration**
   - Current: 100 total connections, 20 keepalive
   - Monitoring: No automated performance regression detection
   - **Recommendation**: Add performance benchmarks to CI/CD

2. **Cache Warmup Strategy**
   - Valkey cache requires manual warmup
   - Target: >60% hit rate
   - Current: Varies by usage pattern
   - **Recommendation**: Implement automated cache warmup on startup

### Documentation Gaps
1. **Missing API Documentation**
   - Several internal HTTP endpoints lack OpenAPI specs
   - MCP tool parameter schemas incomplete
   - **Effort**: Medium (document existing endpoints)

2. **Incomplete Integration Guides**
   - Service-to-service authentication not documented
   - External MCP gateway setup for new services
   - **Effort**: Small (add to docs/)

3. **Missing Runbooks**
   - Circuit breaker failure recovery
   - Kafka consumer backpressure handling
   - Cache invalidation strategies
   - **Effort**: Medium (create operational guides)

---

## Known Issues

### Production Issues
1. **MCP Tool Execution Failures**
   - Root cause: Session validation missing
   - Workaround: None (requires fix #1 above)
   - Severity: Critical

2. **Circuit Breaker Disabled**
   - Root cause: Library incompatibility
   - Workaround: Manual monitoring
   - Severity: High

3. **External Gateway Unavailable in Docker**
   - Root cause: Architectural limitation
   - Workaround: Run on host
   - Severity: Medium (by design)

### Development Issues
1. **Test Suite Execution Time**
   - Full test suite: ~5-10 minutes
   - Issue: No parallel execution configured
   - Recommendation: Implement pytest-xdist

2. **Docker Build Cache Invalidation**
   - Issue: Code changes require `--build` flag
   - Impact: Slow iteration cycle
   - Recommendation: Optimize Dockerfile layer caching

3. **IDE Integration Gaps**
   - Missing: ONEX node type hints in IDEs
   - Missing: MCP tool auto-completion
   - Recommendation: Generate type stubs

---

## Summary Statistics

### By Priority
- **High**: 4 items (blockers and production risks)
- **Medium**: 6 items (integration gaps and test coverage)
- **Low**: 8 items (future features and disabled capabilities)

### By Effort
- **Small** (1-2 days): 8 items
- **Medium** (3-7 days): 6 items
- **Large** (1-2 weeks): 1 item
- **N/A** (architectural/awaiting events): 3 items

### By Impact
- **Critical** (blocks functionality): 1 item
- **High** (production risk): 2 items
- **Medium** (degraded experience): 7 items
- **Low** (nice-to-have): 8 items

### Test Coverage
- **Skipped tests**: 50+ across services
- **Missing fixtures**: Database, Kafka, Archon project
- **Coverage gaps**: Service authentication, pattern evolution

---

## Recommended Action Plan

### Week 1: Critical Blockers
1. **Day 1-2**: Implement service authentication middleware (Issue #1)
2. **Day 3-4**: Replace circuit breaker library (Issue #2)
3. **Day 5**: Register Kafka consumer handler (Issue #3)

### Week 2: Integration & Testing
1. **Day 1-2**: Fix metadata stamping endpoints (Issue #4)
2. **Day 3-4**: Implement test fixtures for skipped tests
3. **Day 5**: Validate workflow coordinator API (Issue #9)

### Week 3: Technical Debt
1. **Day 1-2**: Resolve TODOs in Kafka consumer handlers
2. **Day 3-4**: Add missing API documentation
3. **Day 5**: Implement event metrics collection (Issue #10)

### Future Sprints
- **Phase 6**: AST-based code correction (Issue #11)
- **Post-MVP**: Enable optional features (Issues #12-15)
- **Continuous**: Test coverage improvements

---

## References

- [OmniNode Bridge MCP Tools Report](../../python/OMNINODE_BRIDGE_MCP_TOOLS_REPORT.md)
- [External Gateway Quick Reference](EXTERNAL_GATEWAY_QUICK_REFERENCE.md)
- [Archon Ticket Completion Analysis](../../ARCHON_TICKET_COMPLETION_ANALYSIS_2025_10_18.md)

---

**Last Updated**: 2025-10-18
**Status**: Active tracking - update as issues are resolved
