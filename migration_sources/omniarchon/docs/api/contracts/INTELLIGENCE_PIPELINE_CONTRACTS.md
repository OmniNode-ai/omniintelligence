# Intelligence Pipeline API Contracts

## Overview

This document defines the complete API contracts for the Archon Intelligence Pipeline, including data structures, service interfaces, and data flow between components.

## Data Structures

### Core Intelligence Data Structures

#### `IntelligenceDocumentData`
```python
@dataclass
class IntelligenceDocumentData:
    id: str                                    # Document UUID
    created_at: str                            # ISO timestamp
    repository: str                            # Repository name
    commit_sha: str                            # Git commit hash
    author: str                                # Commit author
    change_type: str                           # Type of change
    diff_analysis: Optional[DiffAnalysisData] # File changes analysis
    temporal_correlations: List[TemporalCorrelationData]
    semantic_correlations: List[SemanticCorrelationData]
    breaking_changes: List[BreakingChangeData]
    security_analysis: Optional[SecurityAnalysisData]
```

#### `SemanticCorrelationData` (Core Structure)
```python
@dataclass
class SemanticCorrelationData:
    repository: str                            # Target repository
    commit_sha: str                            # Target commit
    semantic_similarity: float                 # 0.0-1.0 similarity score
    common_keywords: List[str]                 # Shared concept keywords
    file_information: Optional[Dict[str, Any]] # FILE INFO STRUCTURE BELOW
```

#### `file_information` Structure (Critical for langextract-style analysis)
```python
file_information: {
    "common_files": List[str],              # Exact file matches between repos
    "common_extensions": List[str],         # Shared file extensions (.py, .ts, etc.)
    "common_directories": List[str],        # Shared directory patterns
    "file_overlap_ratio": float,            # 0.0-1.0 file overlap percentage
    "technology_stack": List[str]           # Inferred technologies (Python, TypeScript, etc.)
}
```

## Service Contracts

### 1. Intelligence Document Reader (`intelligence_document_reader.py`)

#### Purpose
Retrieves intelligence documents from Supabase database and converts to structured data objects.

#### Key Methods

##### `get_intelligence_documents()`
```python
def get_intelligence_documents(
    time_range: str = "24h",
    repository_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[IntelligenceDocumentData]:
```

**Input:**
- `time_range`: "1h", "6h", "24h", "72h", "7d"
- `repository_filter`: Optional repository name filter
- `limit`: Maximum documents to return
- `offset`: Pagination offset

**Output:**
- List of `IntelligenceDocumentData` objects with full correlation data

**Critical Implementation:**
```python
# In _parse_correlations() method:
for sc_data in correlation_analysis.get("semantic_correlations", []):
    file_info = sc_data.get("file_information")  # THIS MUST NOT BE NULL
    semantic_correlations.append(SemanticCorrelationData(
        repository=sc_data.get("repository", ""),
        commit_sha=sc_data.get("commit_sha", ""),
        semantic_similarity=sc_data.get("semantic_similarity", 0.0),
        common_keywords=sc_data.get("common_keywords", []),
        file_information=file_info  # MUST PRESERVE FROM DATABASE
    ))
```

### 2. Intelligence Service (`intelligence_service.py`)

#### Purpose
Converts internal data structures to API response models for REST endpoints.

#### API Response Models

##### `SemanticCorrelation` (API Model)
```python
class SemanticCorrelation(BaseModel):
    repository: str
    commit_sha: str
    semantic_similarity: float
    common_keywords: List[str]
    file_information: Optional[Dict[str, Any]] = None  # MUST INCLUDE THIS
```

##### `IntelligenceResponse`
```python
class IntelligenceResponse(BaseModel):
    success: bool
    total_documents: int
    documents: List[IntelligenceDocument]  # Each contains correlation_analysis
```

#### Key Methods

##### `get_intelligence_documents()`
```python
async def get_intelligence_documents(
    repository: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 50,
    offset: int = 0
) -> IntelligenceResponse:
```

**Critical Implementation:**
```python
# In convert_document_data_to_api_model():
semantic_correlations_api = [
    SemanticCorrelation(
        repository=sc.repository,
        commit_sha=sc.commit_sha,
        semantic_similarity=sc.semantic_similarity,
        common_keywords=sc.common_keywords,
        file_information=getattr(sc, 'file_information', None)  # MUST PRESERVE
    )
    for sc in semantic_correlations  # sc MUST have file_information
]
```

### 3. Correlation Generator (`correlation_generator.py`)

#### Purpose
Creates correlation data between intelligence documents using semantic and temporal analysis.

#### Key Methods

##### `generate_semantic_correlation()`
```python
def generate_semantic_correlation(
    doc1: IntelligenceDocumentData,
    doc2: IntelligenceDocumentData
) -> Optional[SemanticCorrelationData]:
```

**Implementation Contract:**
```python
# MUST call this method to get file information:
file_information = self.get_file_information_for_correlation(doc1, doc2)

return SemanticCorrelationData(
    repository=doc2.repository,
    commit_sha=doc2.commit_sha,
    semantic_similarity=similarity_score,
    common_keywords=common_concepts,
    file_information=file_information  # MUST NOT BE NULL
)
```

##### `get_file_information_for_correlation()` (Critical Method)
```python
def get_file_information_for_correlation(
    doc1: IntelligenceDocumentData,
    doc2: IntelligenceDocumentData
) -> Dict[str, Any]:
```

**Guaranteed Output Structure:**
```python
{
    "common_files": List[str],          # Never null, may be empty []
    "common_extensions": List[str],     # Never null, default ["mixed"]
    "common_directories": List[str],    # Never null, may be empty []
    "file_overlap_ratio": float,        # Always 0.0-1.0
    "technology_stack": List[str]       # Never null, default ["Unknown"]
}
```

##### `update_document_correlations()` (Database Storage)
```python
async def update_document_correlations(
    doc_id: str,
    correlations: Dict[str, List]
) -> None:
```

**Storage Contract:**
```python
correlation_data = {
    "semantic_correlations": [
        {
            "repository": sc.repository,
            "commit_sha": sc.commit_sha,
            "semantic_similarity": sc.semantic_similarity,
            "common_keywords": sc.common_keywords,
            "file_information": sc.file_information  # STORED TO DATABASE
        } for sc in correlations['semantic']
    ]
}
```

### 4. Intelligence Document Writer (`intelligence_document_writer.py`)

#### Purpose
Persists correlation data to Supabase database as nested JSON in project documents.

#### Key Methods

##### `update_document_correlations()`
```python
def update_document_correlations(
    document_id: str,
    correlation_data: Dict[str, Any]
) -> Dict[str, Any]:
```

**Database Storage Contract:**
```python
# Stores to: archon_projects.docs[N].content.correlation_analysis
{
    "temporal_correlations": [...],
    "semantic_correlations": [
        {
            "repository": str,
            "commit_sha": str,
            "semantic_similarity": float,
            "common_keywords": List[str],
            "file_information": Dict[str, Any]  # MUST BE PERSISTED AS JSON
        }
    ],
    "breaking_changes": [...]
}
```

## API Endpoints

### GET `/api/intelligence/documents`

**Query Parameters:**
- `repository`: Optional repository filter
- `time_range`: "1h", "6h", "24h", "72h", "7d"
- `limit`: 1-1000 (default: 50)
- `offset`: Pagination offset (default: 0)

**Response Contract:**
```json
{
    "success": true,
    "total_documents": 42,
    "documents": [
        {
            "id": "uuid",
            "created_at": "2025-09-05T16:00:00Z",
            "repository": "archon",
            "commit_sha": "abc123",
            "author": "developer",
            "change_type": "enhanced_code_changes_with_correlation",
            "intelligence_data": {
                "diff_analysis": {
                    "total_changes": 5,
                    "modified_files": ["file1.py", "file2.ts"]
                },
                "correlation_analysis": {
                    "semantic_correlations": [
                        {
                            "repository": "omniagent",
                            "commit_sha": "def456",
                            "semantic_similarity": 0.42,
                            "common_keywords": ["api", "service"],
                            "file_information": {
                                "common_files": [],
                                "common_extensions": ["py", "ts"],
                                "common_directories": ["src"],
                                "file_overlap_ratio": 0.25,
                                "technology_stack": ["Python", "TypeScript"]
                            }
                        }
                    ]
                }
            }
        }
    ]
}
```

### POST `/api/intelligence/force-regenerate-correlations`

**Purpose:** Clear all existing correlations and regenerate with enhanced file analysis.

**Response Contract:**
```json
{
    "success": true,
    "message": "Force correlation regeneration completed successfully",
    "results": {
        "processed_documents": 5,
        "cleared_documents": 20,
        "total_correlations_generated": 8,
        "semantic_correlations": 8,
        "temporal_correlations": 0,
        "breaking_changes": 0
    }
}
```

## Data Flow Validation

### File Information Pipeline
1. **Generation**: `correlation_generator.get_file_information_for_correlation()` creates structured data
2. **Storage**: Data stored as JSON in Supabase `archon_projects.docs[N].content.correlation_analysis.semantic_correlations[N].file_information`
3. **Retrieval**: `intelligence_document_reader._parse_correlations()` extracts `sc_data.get("file_information")`
4. **API Conversion**: `intelligence_service` preserves field via `getattr(sc, 'file_information', None)`
5. **Frontend Display**: React component renders based on `corr.file_information` presence

### Validation Points
- [ ] `file_information` never null after generation
- [ ] Database stores nested JSON correctly
- [ ] Retrieval preserves all fields
- [ ] API response includes complete structure
- [ ] Frontend conditional rendering works

## Known Issues & Solutions

### Issue: `file_information` appears as `null` in API response
**Root Cause**: Data generated correctly but lost during database storage/retrieval
**Debugging**: Check each pipeline stage:
1. Verify generation logs show correct data structure
2. Verify database contains JSON data (not null)
3. Verify retrieval logs show correct parsing
4. Verify API conversion preserves field

### Issue: Empty `modified_files` in documents
**Root Cause**: Documents without actual file changes being used for correlation
**Solution**: Filter or enrich documents with meaningful file data before correlation

## Testing Contracts

### Unit Test Requirements
- [ ] `get_file_information_for_correlation()` returns valid structure
- [ ] Database storage preserves JSON nested objects
- [ ] API model conversion maintains all fields
- [ ] Frontend displays file information when present

### Integration Test Requirements  
- [ ] End-to-end correlation generation with file information
- [ ] API response includes complete correlation data
- [ ] Dashboard displays file-level insights correctly

## Implementation Checklist

- [ ] All dataclasses include `file_information: Optional[Dict[str, Any]]`
- [ ] All database operations preserve nested JSON
- [ ] All API models include file_information field
- [ ] All service methods handle file_information correctly
- [ ] Frontend components render file_information conditionally
