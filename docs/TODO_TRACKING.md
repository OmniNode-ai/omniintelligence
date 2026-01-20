# TODO Tracking

This document tracks TODOs found during PR #10 review for future implementation.

## Protocol Integration TODOs

### OMN-470: Strict Validation Mode
- **File**: `src/omniintelligence/tools/contract_linter.py:709`
- **Description**: Implement strict validation mode for contract linter
- **Planned Features**:
  - Enable path traversal protection
  - Additional validation rules
- **Status**: Backlog

### OMN-471: Schema Version Selection
- **File**: `src/omniintelligence/tools/contract_linter.py:721`
- **Description**: Implement schema version selection for contract linter
- **Planned Features**:
  - Support multiple schema versions (1.0.0, 1.1.0, 2.0.0, etc.)
- **Status**: Backlog

### #13: QualityAnalyzerProtocol Integration
- **File**: `src/omniintelligence/nodes/quality_scoring_compute/contract.yaml:54`
- **Description**: Integrate QualityAnalyzerProtocol from omnibase_spi
- **Phase**: Backlog - Phase 3 (v0.4.0)
- **Status**: Backlog

### #14: EmbeddingModelProtocol Integration
- **File**: `src/omniintelligence/nodes/vectorization_compute/contract.yaml:72`
- **Description**: Integrate EmbeddingModelProtocol from omnibase_spi
- **Phase**: Backlog - Phase 3 (v0.4.0)
- **Status**: Backlog

### #15: IntentClassifierProtocol Integration
- **File**: `src/omniintelligence/nodes/intent_classifier_compute/contract.yaml:39`
- **Description**: Integrate IntentClassifierProtocol from omnibase_spi
- **Phase**: Backlog - Phase 3 (v0.4.0)
- **Status**: Backlog

## Node Implementation TODOs

### NodeIngestionEffect Implementation
- **File**: `src/omniintelligence/nodes/__init__.py:60`
- **Description**: Implement full NodeIngestionEffect node
- **Purpose**: Handle document/code ingestion into the intelligence system
- **Contract**: `nodes/ingestion_effect/contract.yaml`
- **Features**:
  - File reading and preprocessing
  - Vectorization and indexing
  - Entity extraction
  - Publish ingestion events to Kafka
- **Status**: Pending implementation

### NodePatternLearningCompute Implementation
- **File**: `src/omniintelligence/nodes/__init__.py:70`
- **Description**: Implement full NodePatternLearningCompute node
- **Purpose**: Learn patterns from codebase for intelligent suggestions
- **Contract**: `nodes/pattern_learning_compute/contract.yaml`
- **Status**: Pending implementation

## Architecture TODOs

### #16: Intelligence Adapter Split
- **File**: `src/omniintelligence/nodes/intelligence_adapter/contract.yaml:9`
- **Description**: Consider splitting intelligence adapter into smaller, focused adapters
- **Current State**: Handles multiple operation types (quality, pattern, performance)
- **Target Version**: v2.0 (future consideration)
- **Status**: Future consideration

### #17: Event Payload Model Migration
- **File**: `src/omniintelligence/nodes/intelligence_adapter/contract.yaml:54`
- **Description**: Migrate event payload models to canonical location
- **Target Module**: `omniintelligence.events.models`
- **Affected Models**:
  - ModelCodeAnalysisRequestPayload
  - ModelCodeAnalysisCompletedPayload
  - ModelCodeAnalysisFailedPayload
- **Status**: Planned

### #18: Handler Module Creation
- **File**: `src/omniintelligence/nodes/intelligence_adapter/contract.yaml:90`
- **Description**: Create handler modules for intelligence adapter
- **Handlers to Create**:
  - handler_analyze_code.py (HandlerAnalyzeCode)
- **Status**: Planned when needed

### #19: Legacy Module Migration
- **File**: `src/omniintelligence/nodes/intelligence_adapter/contract.yaml:149`
- **Description**: Migrate modules from _legacy to canonical structure
- **Modules to Migrate**:
  - `omniintelligence.clients.client_intelligence_service` (currently in `_legacy/clients/`)
- **Status**: Planned

## Effect Node Handler TODOs

### Qdrant Vector Effect Handlers
- **File**: `src/omniintelligence/nodes/qdrant_vector_effect/contract.yaml:24`
- **Description**: Create handler modules for Qdrant operations
- **Handlers**:
  - handler_qdrant_upsert.py (HandlerQdrantUpsert)
- **Status**: Pending

### Memgraph Graph Effect Handlers
- **File**: `src/omniintelligence/nodes/memgraph_graph_effect/contract.yaml:24`
- **Description**: Create handler modules for Memgraph operations
- **Handlers**:
  - handler_memgraph_create_nodes.py (HandlerMemgraphCreateNodes)
- **Status**: Pending

### PostgreSQL Pattern Effect Handlers
- **File**: `src/omniintelligence/nodes/postgres_pattern_effect/contract.yaml:24`
- **Description**: Create handler modules for PostgreSQL pattern operations
- **Handlers**:
  - handler_postgres_store_pattern.py (HandlerPostgresStorePattern)
- **Status**: Pending

### Intelligence API Effect Handlers
- **File**: `src/omniintelligence/nodes/intelligence_api_effect/contract.yaml:24`
- **Description**: Create handler modules for LLM API operations
- **Handlers**:
  - handler_llm_call.py (HandlerLLMCall)
- **Status**: Pending

## Stub Implementation TODO

### Full Stub Replacements
- **File**: `src/omniintelligence/nodes/intelligence_adapter/node_intelligence_adapter_effect.py:79`
- **Description**: Implement full replacements for stub classes if needed for production
- **Affected Classes**:
  - ModelIntelligenceConfig (stub)
  - IntelligenceServiceClient (stub)
  - EventPublisher (stub)
- **Status**: Pending production need assessment

---

## Priority Levels

| Priority | Description |
|----------|-------------|
| **P0** | Critical - blocks release |
| **P1** | High - needed for feature completion |
| **P2** | Medium - improves quality/maintainability |
| **P3** | Low - nice to have |

## Current Prioritization

1. **P1**: #17 Event Payload Model Migration - Clean architecture
2. **P1**: #19 Legacy Module Migration - Technical debt
3. **P2**: #13, #14, #15 Protocol Integration - Phase 3 work
4. **P2**: Node Implementation (Ingestion, PatternLearning)
5. **P3**: #16 Adapter Split - Future architecture
6. **P3**: Handler module creation - Create when needed

---

*Last updated: 2026-01-19*
*Generated during PR #10 nitpick validator fixes*
