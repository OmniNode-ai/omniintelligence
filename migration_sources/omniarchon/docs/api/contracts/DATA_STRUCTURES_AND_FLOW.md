# Intelligence Data Structures and Flow Contracts

## Overview

This document provides a unified view of all data structures and their flow through the Archon Intelligence Pipeline. It serves as the master reference for understanding how data moves from generation through storage to API responses and frontend display.

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Intelligence Data Pipeline                      │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Generation    │    Storage      │        Retrieval            │
│   (Correlation  │   (Database)    │      (API/Frontend)         │
│   Generator)    │                 │                             │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Correlation   │ • Supabase      │ • Document Reader           │
│   Analysis      │   JSONB         │ • Intelligence Service     │
│ • File Info     │ • Nested JSON   │ • API Response             │
│ • Langextract   │ • Preservation  │ • Frontend Display         │
└─────────────────┴─────────────────┴─────────────────────────────┘

Data Flow:
Generation → Storage → Retrieval → Conversion → API → Frontend
     ↓           ↓          ↓           ↓        ↓       ↓
SemanticCorr → JSON → SemanticCorr → SemanticCorr → JSON → UI
Data         Storage  Data          API Model
```

## Core Data Structures

### Intelligence Document Hierarchy

```
IntelligenceDocument
├── id, created_at, repository, commit_sha, author, change_type
└── intelligence_data
    ├── diff_analysis
    │   ├── total_changes, added_lines, removed_lines
    │   └── modified_files[]
    ├── correlation_analysis
    │   ├── temporal_correlations[]
    │   ├── semantic_correlations[]        ← CONTAINS file_information
    │   └── breaking_changes[]
    └── security_analysis
        ├── patterns_detected[], risk_level
        └── secure_patterns
```

## Data Structure Variations by Layer

### 1. Data Access Layer (`intelligence_data_structures.py`)

#### `SemanticCorrelationData` (Internal Data Structure)
```python
@dataclass
class SemanticCorrelationData:
    repository: str
    commit_sha: str
    semantic_similarity: float                 # 0.0-1.0
    common_keywords: List[str]
    file_information: Optional[Dict[str, Any]] = None  # FILE ANALYSIS DATA
```

#### `IntelligenceDocumentData` (Internal Container)
```python
@dataclass  
class IntelligenceDocumentData:
    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    diff_analysis: Optional[DiffAnalysisData]
    temporal_correlations: List[TemporalCorrelationData]
    semantic_correlations: List[SemanticCorrelationData]    # Contains file_information
    breaking_changes: List[BreakingChangeData]
    security_analysis: Optional[SecurityAnalysisData]
```

### 2. Database Storage Layer (Supabase JSONB)

#### Storage Location: `archon_projects.docs[N].content.correlation_analysis`
```json
{
    "temporal_correlations": [...],
    "semantic_correlations": [
        {
            "repository": "omniagent",
            "commit_sha": "abc123",
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
    ],
    "breaking_changes": [...]
}
```

### 3. API Service Layer (`intelligence_service.py`)

#### `SemanticCorrelation` (API Response Model)
```python
class SemanticCorrelation(BaseModel):
    repository: str
    commit_sha: str  
    semantic_similarity: float
    common_keywords: List[str]
    file_information: Optional[Dict[str, Any]] = None  # PRESERVED FROM DATA LAYER
```

#### `IntelligenceDocument` (API Response Container)
```python
class IntelligenceDocument(BaseModel):
    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    intelligence_data: IntelligenceData
        └── correlation_analysis: CorrelationAnalysis
            └── semantic_correlations: List[SemanticCorrelation]
```

### 4. Frontend Layer (React TypeScript)

#### TypeScript Interface
```typescript
interface SemanticCorrelation {
    repository: string;
    commit_sha: string;
    semantic_similarity: number;
    common_keywords: string[];
    file_information: FileInformation | null;
}

interface FileInformation {
    common_files: string[];
    common_extensions: string[];
    common_directories: string[];
    file_overlap_ratio: number;
    technology_stack: string[];
}
```

## File Information Structure (Critical Path)

### Complete File Information Schema

```typescript
interface FileInformation {
    // Exact file matches between repositories
    common_files: string[];                    // ["package.json", "src/api/service.py"]

    // File extensions from all files in correlation
    common_extensions: string[];               // ["py", "ts", "json"] (no dots)

    // Directory patterns found in both repositories  
    common_directories: string[];              // ["src", "api", "components"]

    // Percentage of file overlap (0.0-1.0)
    file_overlap_ratio: number;                // 0.25 = 25% overlap

    // Inferred technology stack from file extensions
    technology_stack: string[];                // ["Python", "TypeScript", "React"]
}
```

### File Information Generation Logic

```python
# In correlation_generator.py - get_file_information_for_correlation()

# 1. Collect files from both documents
files1 = set(doc1.diff_analysis.modified_files if doc1.diff_analysis else [])
files2 = set(doc2.diff_analysis.modified_files if doc2.diff_analysis else [])

# 2. Technology stack inference
ext_tech_map = {
    'py': 'Python',
    'ts': 'TypeScript',
    'tsx': 'React/TypeScript',
    'js': 'JavaScript',
    'jsx': 'React/JavaScript',
    'rs': 'Rust',
    'toml': 'Configuration',
    'json': 'Configuration'
}

# 3. Calculate overlap ratio
if files1 and files2:
    common_files = files1.intersection(files2)
    total_files = files1.union(files2)
    file_overlap_ratio = len(common_files) / len(total_files)

# 4. Prevent empty structures
if not any([common_files, common_extensions, common_directories, technology_stack]):
    file_information["technology_stack"] = ["Unknown"]
    file_information["common_extensions"] = ["mixed"]
```

## Data Preservation Contracts

### Critical Preservation Points

1. **Generation → Storage**
   ```python
   # In correlation_generator.py
   file_information = self.get_file_information_for_correlation(doc1, doc2)
   logger.info(f"🔍 Generated file_information for {doc2.repository}: {file_information}")

   return SemanticCorrelationData(
       repository=doc2.repository,
       commit_sha=doc2.commit_sha,
       semantic_similarity=round(min(semantic_similarity, 0.85), 3),
       common_keywords=common_concepts[:5],
       file_information=file_information  # MUST NOT BE NULL
   )
   ```

2. **Storage → Database**
   ```python
   # In intelligence_document_writer.py
   document["content"]["correlation_analysis"] = correlation_data
   # Where correlation_data includes:
   {
       "semantic_correlations": [
           {
               "repository": sc.repository,
               "commit_sha": sc.commit_sha,
               "semantic_similarity": sc.semantic_similarity,
               "common_keywords": sc.common_keywords,
               "file_information": sc.file_information  # STORED AS NESTED JSON
           }
       ]
   }
   ```

3. **Database → Retrieval**
   ```python
   # In intelligence_document_reader.py
   for sc_data in correlation_analysis.get("semantic_correlations", []):
       file_info = sc_data.get("file_information")
       logger.info(f"📥 Retrieved file_information from DB for {sc_data.get('repository')}: {file_info}")
       semantic_correlations.append(SemanticCorrelationData(
           repository=sc_data.get("repository", ""),
           commit_sha=sc_data.get("commit_sha", ""),
           semantic_similarity=sc_data.get("semantic_similarity", 0.0),
           common_keywords=sc_data.get("common_keywords", []),
           file_information=file_info  # PRESERVE FROM DATABASE
       ))
   ```

4. **Retrieval → API Conversion**
   ```python
   # In intelligence_service.py - convert_document_data_to_api_model()
   semantic_correlations = [
       SemanticCorrelation(
           repository=sc.repository,
           commit_sha=sc.commit_sha,
           semantic_similarity=sc.semantic_similarity,
           common_keywords=sc.common_keywords,
           file_information=getattr(sc, 'file_information', None)  # CRITICAL PRESERVATION
       )
       for sc in doc_data.semantic_correlations
   ]
   ```

5. **API → Frontend**
   ```json
   // HTTP Response
   {
       "success": true,
       "documents": [
           {
               "intelligence_data": {
                   "correlation_analysis": {
                       "semantic_correlations": [
                           {
                               "repository": "omniagent",
                               "semantic_similarity": 0.42,
                               "file_information": {
                                   "technology_stack": ["Python", "TypeScript"],
                                   "common_extensions": ["py", "ts"],
                                   "file_overlap_ratio": 0.25
                               }
                           }
                       ]
                   }
               }
           }
       ]
   }
   ```

6. **Frontend → Display**
   ```tsx
   // In IntelligencePage.tsx
   {corr.file_information && (
       <div className="flex items-center space-x-3 text-xs text-gray-500 ml-4">
           {corr.file_information.technology_stack && corr.file_information.technology_stack.length > 0 && (
               <div className="flex items-center space-x-1">
                   <span className="text-gray-400">Tech:</span>
                   <span>{corr.file_information.technology_stack.slice(0, 2).join(', ')}</span>
               </div>
           )}
       </div>
   )}
   ```

## Data Validation Contracts

### Input Validation
- [ ] `semantic_similarity` must be between 0.0 and 1.0
- [ ] `file_overlap_ratio` must be between 0.0 and 1.0  
- [ ] `common_keywords` must be non-null array (can be empty)
- [ ] `technology_stack` must be non-null array (can be empty)
- [ ] All string fields must be non-null (can be empty)

### Output Validation
- [ ] `file_information` must be either valid object or null (never undefined)
- [ ] All array fields in file_information must be arrays (never null)
- [ ] All numeric fields must be valid numbers (not NaN or Infinity)
- [ ] All timestamp strings must be valid ISO 8601 format

### Database Storage Validation
- [ ] JSON structure must be valid and parseable
- [ ] Nested objects must preserve all fields
- [ ] Arrays must maintain ordering
- [ ] Numeric precision must be preserved

## Error Scenarios and Handling

### Common Error Scenarios

1. **file_information appears as null in API**
   - **Root Cause**: Data lost during database storage/retrieval or conversion
   - **Debug Strategy**: Check each pipeline stage with debug logging
   - **Prevention**: Validate at each layer that file_information is preserved

2. **Empty or meaningless file information**
   - **Root Cause**: Documents have no modified_files or empty file data
   - **Solution**: Apply fallback values: `["Unknown"]` for technology_stack, `["mixed"]` for extensions

3. **Hard-coded correlation values (100%)**
   - **Root Cause**: Old temporal correlation data with fixed 1.0 values
   - **Solution**: Use force regeneration to clear old data and generate realistic values

4. **Technology stack shows "Unknown" for all correlations**
   - **Root Cause**: File extension mapping incomplete or files not analyzed
   - **Solution**: Enhance `ext_tech_map` and ensure file analysis runs

## Performance Optimization Contracts

### Memory Management
- **Concept Limiting**: Maximum 5 common concepts per correlation
- **File Limiting**: Maximum 5 common files, 3 directories per correlation
- **Technology Stack**: Maximum 4 technologies per correlation
- **Batch Size**: Process maximum 1000 documents per batch operation

### Query Optimization
- **Time Window Filtering**: Use appropriate time ranges to limit dataset size
- **Repository Exclusion**: Skip same-repository comparisons during correlation generation
- **Threshold Filtering**: Apply intelligent thresholds to reduce low-value correlations

### Caching Strategy
- **Document Reader**: Singleton pattern for database client connections
- **Repository Lists**: Cache active repository list for performance
- **File Extension Mapping**: Static mapping for technology inference

## Testing and Validation Procedures

### End-to-End Testing
1. **Generate Test Data**: Create documents with known file patterns
2. **Force Regeneration**: Clear all correlations and regenerate with new system
3. **Validate Storage**: Check database contains file_information as nested JSON
4. **Test API Response**: Verify API returns file_information correctly
5. **Frontend Validation**: Confirm dashboard displays file information

### Debug Validation Steps
```bash
# 1. Check correlation generation
curl -X POST "http://localhost:8181/api/intelligence/force-regenerate-correlations"

# 2. Check API response structure  
curl -s "http://localhost:8181/api/intelligence/documents?limit=1" | \
jq '.documents[0].intelligence_data.correlation_analysis.semantic_correlations[0]'

# 3. Verify file_information presence
curl -s "http://localhost:8181/api/intelligence/documents" | \
jq '.documents[].intelligence_data.correlation_analysis.semantic_correlations[] | select(.file_information != null)'
```

## Success Criteria Summary

### Data Structure Integrity
- [ ] All layers preserve file_information without data loss
- [ ] JSON serialization/deserialization maintains nested structure
- [ ] Type conversions maintain data fidelity across layers
- [ ] Arrays and objects are never null when they should contain data

### File Information Quality
- [ ] Technology stack contains meaningful technologies (not just "Unknown")
- [ ] File extensions are properly extracted and formatted
- [ ] File overlap ratios are calculated correctly (0.0-1.0 range)
- [ ] Common files and directories are identified accurately

### Correlation Realism
- [ ] Semantic similarity values between 0.0-0.85 (no perfect 1.0 values)  
- [ ] Temporal correlation strength between 0.0-0.95 (realistic variance applied)
- [ ] Common keywords extracted meaningfully from content analysis
- [ ] Breaking changes detected appropriately

### Frontend Display
- [ ] File information displays correctly in React dashboard
- [ ] Technology stack, file extensions, and overlap percentages show
- [ ] Conditional rendering works properly (shows when data present, hides when null)
- [ ] Visual formatting matches design specifications

This comprehensive contract system ensures data integrity and proper flow from generation through to frontend display, with specific focus on preserving the critical `file_information` structure that enables langextract-style analysis and meaningful correlation insights.
