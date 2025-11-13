# Intelligence Service API Contracts

## Overview

This document defines the API contracts for the Intelligence Service, which serves as the presentation layer for intelligence operations. The service provides API response formatting using Pydantic models and integration with the intelligence data access layer.

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Intelligence Service Layer                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   API Models    │   Conversion    │        Data Access          │
│  (Pydantic)     │   Functions     │       Integration           │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • IntelligenceDocument          │ • IntelligenceDataAccess   │
│ • SemanticCorrelation           │ • QueryParameters           │
│ • TemporalCorrelation           │ • IntelligenceDocumentData │
│ • IntelligenceResponse          │ • Database Client           │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Core API Models

### Request/Response Models

#### `IntelligenceResponse` (Main API Response)
```python
class IntelligenceResponse(BaseModel):
    documents: List[IntelligenceDocument]
    total_count: int
    filtered_count: int  
    time_range: str
    repositories: List[str]
```

#### `IntelligenceDocument` (Document Container)
```python
class IntelligenceDocument(BaseModel):
    id: str                                    # Document UUID
    created_at: str                            # ISO timestamp
    repository: str                            # Repository name  
    commit_sha: str                            # Git commit hash
    author: str                                # Commit author
    change_type: str                           # Type of change
    intelligence_data: IntelligenceData        # Nested intelligence analysis
```

#### `IntelligenceData` (Analysis Container)
```python
class IntelligenceData(BaseModel):
    diff_analysis: Optional[DiffAnalysis]
    correlation_analysis: Optional[CorrelationAnalysis]
    security_analysis: Optional[SecurityAnalysis]
```

### Correlation Models (Critical for File Information Display)

#### `SemanticCorrelation` (API Model)
```python
class SemanticCorrelation(BaseModel):
    repository: str                            # Target repository
    commit_sha: str                            # Target commit
    semantic_similarity: float                 # 0.0-1.0 similarity score
    common_keywords: List[str]                 # Shared concept keywords
    file_information: Optional[Dict[str, Any]] = None  # FILE INFO - MUST PRESERVE
```

**Critical Implementation Note:**
```python
# In convert_document_data_to_api_model() - line 142-151
semantic_correlations = [
    SemanticCorrelation(
        repository=sc.repository,
        commit_sha=sc.commit_sha,
        semantic_similarity=sc.semantic_similarity,
        common_keywords=sc.common_keywords,
        file_information=getattr(sc, 'file_information', None)  # MUST PRESERVE FROM DATA LAYER
    )
    for sc in doc_data.semantic_correlations
]
```

#### `TemporalCorrelation` (API Model)
```python
class TemporalCorrelation(BaseModel):
    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float
```

#### `CorrelationAnalysis` (Container)
```python
class CorrelationAnalysis(BaseModel):
    temporal_correlations: List[TemporalCorrelation]
    semantic_correlations: List[SemanticCorrelation]  # Contains file_information
    breaking_changes: List[BreakingChange]
```

### Statistics Models

#### `IntelligenceStats`
```python
class IntelligenceStats(BaseModel):
    total_changes: int
    total_correlations: int
    average_correlation_strength: float
    breaking_changes: int
    repositories_active: int
    time_range: str
```

## Service Methods

### Document Retrieval

#### `get_intelligence_documents()`
```python
async def get_intelligence_documents(
    repository: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 50,
    offset: int = 0
) -> IntelligenceResponse:
```

**Purpose**: Get intelligence documents with optional filtering
**Input Parameters**:
- `repository`: Optional repository filter
- `time_range`: "1h", "6h", "24h", "72h", "7d" (default: "24h")
- `limit`: Maximum documents to return (default: 50)
- `offset`: Pagination offset (default: 0)

**Output**: `IntelligenceResponse` with typed document data

**Critical Implementation**:
```python
# Uses data access layer for retrieval
data_access = get_intelligence_data_access()
params = QueryParameters(repository=repository, time_range=time_range, limit=limit, offset=offset)

# Gets parsed documents and converts to API models
documents_data = data_access.get_parsed_documents(params)
documents = [convert_document_data_to_api_model(doc_data) for doc_data in documents_data]
```

#### `get_intelligence_documents_from_db()` (Legacy Compatibility)
```python
async def get_intelligence_documents_from_db(
    repository: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
```

**Purpose**: Backward compatibility wrapper for raw data access
**Returns**: Raw dictionary data for processing by different layers

### Statistics

#### `get_intelligence_stats()`
```python
async def get_intelligence_stats(
    repository: Optional[str] = None,
    time_range: str = "24h"
) -> IntelligenceStats:
```

**Purpose**: Get aggregated statistics about intelligence activity
**Returns**: Typed `IntelligenceStats` with all metrics

#### `calculate_intelligence_stats()` (Legacy Compatibility)
```python
async def calculate_intelligence_stats(
    repository: Optional[str] = None,
    time_range: str = "24h"
) -> Dict[str, Any]:
```

**Purpose**: Shared function for both API and WebSocket handlers
**Returns**: Raw dictionary data for backward compatibility

### Repository Management

#### `get_active_repositories()`
```python
async def get_active_repositories() -> List[str]:
```

**Purpose**: Get list of repositories that have generated intelligence data
**Returns**: Sorted list of repository names

## Data Conversion Functions

### Core Conversion Method

#### `convert_document_data_to_api_model()`
```python
def convert_document_data_to_api_model(doc_data: IntelligenceDocumentData) -> IntelligenceDocument:
```

**Purpose**: Convert data access model to API response model
**Critical Responsibility**: Preserve `file_information` field during conversion

**File Information Preservation Contract**:
```python
# MUST use getattr to preserve file_information from data layer
semantic_correlations = [
    SemanticCorrelation(
        repository=sc.repository,
        commit_sha=sc.commit_sha,
        semantic_similarity=sc.semantic_similarity,
        common_keywords=sc.common_keywords,
        file_information=getattr(sc, 'file_information', None)  # CRITICAL: PRESERVE FROM DATA
    )
    for sc in doc_data.semantic_correlations
]
```

#### `convert_stats_data_to_api_model()`
```python
def convert_stats_data_to_api_model(stats_data: IntelligenceStatsData, time_range: str) -> IntelligenceStats:
```

**Purpose**: Convert data access stats model to API response model

### Legacy Conversion

#### `parse_intelligence_content()` (Deprecated)
```python
def parse_intelligence_content(content: Dict[str, Any]) -> IntelligenceData:
```

**Purpose**: Backward compatibility wrapper for content parsing
**Note**: Delegates to data access layer for actual parsing

## Data Flow Contracts

### Request → Response Flow

```
1. API Request (FastAPI endpoint)
   ↓
2. get_intelligence_documents(repository, time_range, limit, offset)
   ↓
3. QueryParameters → IntelligenceDataAccess.get_parsed_documents()
   ↓
4. IntelligenceDocumentData[] → convert_document_data_to_api_model()
   ↓
5. IntelligenceDocument[] → IntelligenceResponse
   ↓
6. JSON Response to Client
```

### File Information Flow (Critical Path)

```
1. SemanticCorrelationData.file_information (from data layer)
   ↓
2. getattr(sc, 'file_information', None) (in conversion)
   ↓
3. SemanticCorrelation.file_information (API model)
   ↓
4. JSON Response with file_information object
   ↓
5. Frontend conditional rendering based on presence
```

## Error Handling Contracts

### Service-Level Error Handling

```python
# Pattern used across all async methods
try:
    # Service logic
    return successful_response
except Exception as e:
    logger.error(f"Error in service method: {e}")
    return empty_response_with_defaults
```

### Default Responses

#### Document Retrieval Errors
```python
IntelligenceResponse(
    documents=[],
    total_count=0,
    filtered_count=0,
    time_range=time_range,
    repositories=[]
)
```

#### Statistics Calculation Errors
```python
IntelligenceStats(
    total_changes=0,
    total_correlations=0,
    average_correlation_strength=0.0,
    breaking_changes=0,
    repositories_active=0,
    time_range=time_range
)
```

## Integration Points

### With Intelligence Data Access Layer

```python
# Singleton pattern for data access
_data_access_instance = None

def get_intelligence_data_access() -> IntelligenceDataAccess:
    global _data_access_instance
    if _data_access_instance is None:
        client = get_database_client()
        _data_access_instance = create_intelligence_data_access(client)
    return _data_access_instance
```

### With FastAPI Endpoints

**Expected Usage in API Routes:**
```python
from ..services.intelligence_service import get_intelligence_documents

@router.get("/documents")
async def get_documents(repository: str = None, time_range: str = "24h"):
    response = await get_intelligence_documents(
        repository=repository,
        time_range=time_range,
        limit=50,
        offset=0
    )
    return {
        "success": True,
        "total_documents": response.total_count,
        "documents": [doc.dict() for doc in response.documents]
    }
```

## Validation Requirements

### Input Validation
- [ ] `time_range` must be one of: "1h", "6h", "24h", "72h", "7d"
- [ ] `limit` must be between 1 and 1000
- [ ] `offset` must be non-negative
- [ ] `repository` must exist in active repositories list (when provided)

### Output Validation  
- [ ] All `IntelligenceDocument` objects have non-empty `id` fields
- [ ] `semantic_similarity` values are between 0.0 and 1.0
- [ ] `file_information` is either `null` or valid JSON object
- [ ] `created_at` timestamps are valid ISO 8601 strings
- [ ] `correlation_strength` values are between 0.0 and 1.0

## File Information Debugging

### Critical Debugging Points

1. **Data Layer Input**: Verify `IntelligenceDocumentData.semantic_correlations[].file_information` is not null
2. **Conversion Function**: Check `getattr(sc, 'file_information', None)` returns expected data
3. **API Model**: Confirm `SemanticCorrelation.file_information` contains the data
4. **JSON Serialization**: Verify Pydantic serialization preserves nested objects

### Debug Logging Recommendations

```python
# Add to convert_document_data_to_api_model()
for sc in doc_data.semantic_correlations:
    file_info = getattr(sc, 'file_information', None)
    logger.info(f"🔄 Converting semantic correlation for {sc.repository}: file_information={file_info}")
```

## Performance Considerations

### Caching Strategy
- **Data Access Instance**: Singleton pattern prevents repeated database client creation
- **Repository List**: Consider caching active repositories list for performance

### Batch Processing
- **Large Datasets**: Use pagination to prevent memory issues
- **Conversion Optimization**: Batch convert documents to reduce overhead

## Testing Contracts

### Unit Test Requirements
- [ ] Test `convert_document_data_to_api_model()` preserves `file_information`
- [ ] Test error handling returns proper default responses
- [ ] Test pagination parameters are correctly passed to data layer
- [ ] Test repository filtering works correctly

### Integration Test Requirements
- [ ] Test end-to-end document retrieval with file information
- [ ] Test statistics calculation with real data
- [ ] Test backward compatibility methods work correctly
- [ ] Test error propagation from data access layer

## Success Criteria

### File Information Display Working
- [ ] API response contains `file_information` object (not null)
- [ ] Object includes: `technology_stack`, `common_extensions`, `file_overlap_ratio`
- [ ] Values are meaningful (not defaults like ["Unknown"])
- [ ] Frontend receives and displays file information correctly
