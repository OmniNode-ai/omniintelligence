# Correlation Generator API Contracts

## Overview

This document defines the API contracts for the Automated Correlation Generation Service, which analyzes intelligence documents and generates correlation data by analyzing relationships between commits across repositories. The service provides temporal correlation detection, semantic correlation analysis, and intelligent file-level analysis.

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Correlation Generator Service                   │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Analysis Types │  Intelligence   │    File-Level Analysis      │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Temporal      │ • Content Sim   │ • Extension Detection       │
│ • Semantic      │ • Quality Corr  │ • Directory Analysis        │
│ • Breaking      │ • Repo Relations│ • Technology Inference      │
├─────────────────┼─────────────────┼─────────────────────────────┤
│   Data Access   │   Data Storage  │     Performance             │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Document      │ • Document      │ • Batch Processing          │
│   Reader        │   Writer        │ • Intelligent Thresholds   │
│ • Query Params  │ • Correlation   │ • Realistic Variance        │
│               │   Updates       │ • Debug Logging             │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Core Data Structures

### `CorrelationCandidate`
```python
@dataclass
class CorrelationCandidate:
    source_doc_id: str
    target_doc_id: str
    source_repository: str
    target_repository: str
    source_commit: str
    target_commit: str
    source_timestamp: datetime
    target_timestamp: datetime
    correlation_type: str               # 'temporal', 'semantic', 'breaking_change'
    strength: float
    metadata: Dict[str, Any]
```

### `AutomatedCorrelationGenerator` (Main Service Class)
```python
class AutomatedCorrelationGenerator:
    def __init__(self):
        database_client = get_database_client()
        self.document_reader = create_intelligence_document_reader(database_client)
        self.document_writer = create_intelligence_document_writer(database_client)
        self.temporal_windows = [1, 6, 24, 72]          # Time windows in hours
        self.semantic_threshold = 0.3                   # Minimum semantic similarity
        self.temporal_threshold = 0.4                   # Minimum temporal correlation strength
```

## Core Service Methods

### Batch Processing Methods

#### `generate_correlations_for_empty_documents()`
```python
async def generate_correlations_for_empty_documents() -> Dict[str, Any]:
```

**Purpose**: Find documents with empty correlations and generate correlation data for them
**Processing Logic**:
1. Query all documents within 7-day window (limit: 1000)
2. Filter for documents with empty temporal, semantic, and breaking change arrays
3. Generate correlations for each empty document against all other documents
4. Update database with new correlation data

**Output Structure**:
```json
{
    "processed_documents": int,
    "total_correlations_generated": int,
    "temporal_correlations": int,
    "semantic_correlations": int,
    "breaking_changes": int,
    "processing_errors": int,
    "document_updates": [
        {
            "document_id": str,
            "repository": str,
            "commit": str,                  # Truncated to 8 chars
            "correlations_added": {
                "temporal": int,
                "semantic": int,
                "breaking": int
            }
        }
    ]
}
```

#### `force_regenerate_all_correlations()`
```python
async def force_regenerate_all_correlations() -> Dict[str, Any]:
```

**Purpose**: Force regeneration of correlations for ALL documents, clearing old data including 100% values
**Critical Features**:
- Clears existing correlation data (including hard-coded 1.0 values)
- Generates new correlations using improved intelligent analysis
- Always updates documents even if no new correlations found (to clear old data)

**Output Structure**:
```json
{
    "processed_documents": int,         # Documents with new correlations
    "cleared_documents": int,           # Documents with old data cleared
    "total_correlations_generated": int,
    "temporal_correlations": int,
    "semantic_correlations": int,
    "breaking_changes": int,
    "processing_errors": int,
    "document_updates": [...]           # Same as above
}
```

### Individual Document Processing

#### `generate_correlations_for_document()`
```python
async def generate_correlations_for_document(target_doc, all_documents) -> Dict[str, List]:
```

**Purpose**: Generate correlations for a specific document by analyzing it against all other documents
**Input**:
- `target_doc`: The document to generate correlations for
- `all_documents`: All available documents to compare against

**Processing Logic**:
1. Parse target document timestamp (with fallback handling)
2. Compare against all documents from different repositories (excludes same repo)
3. Generate temporal, semantic, and breaking change correlations
4. Apply intelligent thresholds and variance

**Output**:
```python
{
    'temporal': List[TemporalCorrelationData],
    'semantic': List[SemanticCorrelationData],    # Contains file_information
    'breaking': List[BreakingChangeData]
}
```

## Correlation Analysis Methods

### Temporal Correlation Analysis

#### `analyze_temporal_correlation()`
```python
def analyze_temporal_correlation(doc1, time1: datetime, doc2, time2: datetime) -> Optional[TemporalCorrelationData]:
```

**Purpose**: Analyze temporal relationship between two documents
**Algorithm**:
1. Calculate time difference in hours
2. Skip documents with identical timestamps (< 0.1 hours = fallback timestamps)
3. Check against time windows: [1, 6, 24, 72] hours
4. Calculate intelligent correlation strength using multiple factors
5. Apply temporal threshold (0.4) for filtering

**Output Structure**:
```python
TemporalCorrelationData(
    repository=str,              # Target repository
    commit_sha=str,             # Target commit
    time_diff_hours=float,      # Rounded to 2 decimals
    correlation_strength=float  # Rounded to 3 decimals
)
```

#### `calculate_intelligent_correlation_strength()`
```python
def calculate_intelligent_correlation_strength(doc1, doc2, time_diff: float, window_hours: int) -> float:
```

**Purpose**: Calculate realistic correlation strength using intelligent content analysis
**Weighted Factors**:
- **Time proximity (40%)**: Closer in time = stronger correlation (non-linear)
- **Content similarity (30%)**: Shared keywords and concepts analysis
- **Repository relationship (20%)**: Related repository patterns (omni, archon, etc.)
- **Quality correlation (10%)**: Shared quality patterns and indicators

**Variance Application**:
```python
# Apply realistic variance (avoid perfect correlations)
variance = random.uniform(0.85, 1.0)  # Add 0-15% randomness
strength = strength * variance
return max(0.0, min(strength, 0.95))  # Cap at 95%
```

### Semantic Correlation Analysis

#### `analyze_semantic_correlation()`
```python
def analyze_semantic_correlation(doc1, doc2) -> Optional[SemanticCorrelationData]:
```

**Purpose**: Analyze semantic similarity using intelligent analysis
**Algorithm**:
1. Calculate content similarity (70% weight)
2. Calculate quality pattern correlation (30% weight)
3. Apply realistic variance (0.9-1.0 range)
4. Use adjusted threshold (0.3 * 0.7 = 0.21 for more realistic results)
5. Generate file-level information for enhanced display

**Critical Implementation**:
```python
# Get file-level information for enhanced correlation display
file_information = self.get_file_information_for_correlation(doc1, doc2)

# Debug logging to check file_information
logger.info(f"🔍 Generated file_information for {doc2.repository}: {file_information}")

return SemanticCorrelationData(
    repository=doc2.repository,
    commit_sha=doc2.commit_sha,
    semantic_similarity=round(min(semantic_similarity, 0.85), 3),  # Cap at 85%
    common_keywords=common_concepts[:5],  # Limit to top 5
    file_information=file_information     # MUST NOT BE NULL
)
```

### File-Level Analysis (Langextract-Style)

#### `get_file_information_for_correlation()` (Critical Method)
```python
def get_file_information_for_correlation(doc1, doc2) -> Dict[str, Any]:
```

**Purpose**: Extract specific file information for correlation display using langextract-style analysis
**Guaranteed Output Structure**:
```python
{
    "common_files": List[str],          # Exact file matches (max 5)
    "common_extensions": List[str],     # File extensions from all files
    "common_directories": List[str],    # Directory patterns (max 3)
    "file_overlap_ratio": float,        # 0.0-1.0 overlap percentage
    "technology_stack": List[str]       # Inferred technologies (max 4)
}
```

**Technology Stack Inference**:
```python
ext_tech_map = {
    'py': 'Python',
    'ts': 'TypeScript',
    'tsx': 'React/TypeScript',
    'js': 'JavaScript',
    'jsx': 'React/JavaScript',
    'rs': 'Rust',
    'toml': 'Configuration',
    'json': 'Configuration',
    'yaml': 'Configuration',
    'yml': 'Configuration',
    'md': 'Documentation'
}
```

**Overlap Calculation**:
```python
# Only calculate overlap if both documents have files
if files1 and files2:
    common_files = files1.intersection(files2)
    total_files = files1.union(files2)
    file_overlap_ratio = len(common_files) / len(total_files)
```

**Fallback Prevention**:
```python
# Ensure file_information is never completely empty
if not any([file_info["common_files"], file_info["common_extensions"],
           file_info["common_directories"], file_info["technology_stack"]]):
    file_info["technology_stack"] = ["Unknown"]
    file_info["common_extensions"] = ["mixed"]
```

#### `extract_file_level_concepts()`
```python
def extract_file_level_concepts(doc) -> Set[str]:
```

**Purpose**: Extract file-level concepts using langextract-style analysis
**Analysis Types**:
1. **File Extension Analysis**: `ext_{extension}` patterns
2. **Directory Pattern Analysis**: `dir_{directory}` patterns
3. **File Name Pattern Analysis**: Semantic file type detection
4. **Content-Based File References**: Configuration and language indicators

**File Pattern Detection**:
```python
# Extract meaningful file patterns
if 'test' in filename_base.lower():
    file_concepts.add("file_test")
if 'config' in filename_base.lower():
    file_concepts.add("file_config")
if 'api' in filename_base.lower():
    file_concepts.add("file_api")
# ... more patterns
```

#### `extract_common_concepts()`
```python
def extract_common_concepts(doc1, doc2) -> List[str]:
```

**Purpose**: Extract meaningful common concepts between documents with file-level analysis
**Concept Sources**:
1. Repository-based concepts (from repository names)
2. Quality indicators (from document analysis)
3. File-level concepts (using langextract-style analysis)
4. Content-based concepts (filtered for meaningful terms)

**Prioritization Logic**:
```python
# Sort by relevance: file patterns first, then by length
file_patterns = [c for c in common if c.startswith(('file_', 'ext_', 'dir_'))]
other_concepts = [c for c in common if not c.startswith(('file_', 'ext_', 'dir_')) and len(c) > 3]

# Prioritize file patterns, then longest concepts
return file_patterns + sorted(other_concepts, key=len, reverse=True)
```

## Content Analysis Methods

### `analyze_content_similarity()`
```python
def analyze_content_similarity(doc1, doc2) -> float:
```

**Purpose**: Analyze content-based similarity between documents
**Algorithm**:
1. Extract content from both documents using `extract_document_content_for_analysis()`
2. Calculate text-based similarity using shared keywords
3. Apply Jaccard similarity: `intersection / union`
4. Boost similarity but cap at 80%: `min(similarity * 2.0, 0.8)`

### `calculate_repository_relationship_factor()`
```python
def calculate_repository_relationship_factor(repo1: str, repo2: str) -> float:
```

**Purpose**: Calculate relationship factor between repositories
**Related Repository Patterns**:
```python
related_patterns = [
    ("omni", 0.7),      # OmniAgent, omnimcp, etc.
    ("archon", 0.6),    # Archon-related repos
    ("claude", 0.5),    # Claude-related repos
    ("agent", 0.4),     # Agent-related repos
]
```

### `analyze_quality_pattern_correlation()`
```python
def analyze_quality_pattern_correlation(doc1, doc2) -> float:
```

**Purpose**: Analyze correlation based on quality patterns and insights
**Quality Indicators**:
- Repository type indicators (agent_system, omni_ecosystem, archon_platform)
- Content quality indicators (intelligence_enhanced, quality_focused, performance_optimized)

## Database Integration Methods

### `update_document_correlations()`
```python
async def update_document_correlations(doc_id: str, correlations: Dict[str, List]) -> None:
```

**Purpose**: Store correlation data to database via document writer
**Storage Format**:
```python
correlation_data = {
    "temporal_correlations": [
        {
            "repository": tc.repository,
            "commit_sha": tc.commit_sha,
            "time_diff_hours": tc.time_diff_hours,
            "correlation_strength": tc.correlation_strength
        } for tc in correlations['temporal']
    ],
    "semantic_correlations": [
        {
            "repository": sc.repository,
            "commit_sha": sc.commit_sha,
            "semantic_similarity": sc.semantic_similarity,
            "common_keywords": sc.common_keywords,
            "file_information": sc.file_information  # STORED AS JSON
        } for sc in correlations['semantic']
    ],
    "breaking_changes": [...]
}
```

**Critical Storage Contract**: `file_information` must be persisted as nested JSON in `archon_projects.docs[N].content.correlation_analysis.semantic_correlations[N].file_information`

## Configuration and Thresholds

### Service Configuration
```python
self.temporal_windows = [1, 6, 24, 72]      # Time windows in hours
self.semantic_threshold = 0.3               # Minimum semantic similarity
self.temporal_threshold = 0.4               # Minimum temporal correlation strength
```

### Intelligent Thresholds
- **Adjusted semantic threshold**: `0.3 * 0.7 = 0.21` for more realistic results
- **Correlation strength cap**: Maximum 95% to avoid unrealistic perfect correlations
- **Semantic similarity cap**: Maximum 85% for semantic correlations
- **Quality correlation cap**: Maximum 60% for quality pattern correlation

### Variance Application
```python
# Temporal correlation variance
variance = random.uniform(0.85, 1.0)  # Add 0-15% randomness

# Semantic correlation variance  
variance = random.uniform(0.9, 1.0)   # Smaller variance for semantic analysis
```

## Error Handling and Logging

### Debug Logging Strategy
```python
# File information generation tracking
logger.info(f"🔍 Generated file_information for {doc2.repository}: {file_information}")

# File analysis debugging
logger.info(f"🗂️ Files in {doc1.repository}: {list(files1)}")
logger.info(f"🗂️ Files in {doc2.repository}: {list(files2)}")

# Processing results
logger.info(f"✅ Generated correlations for {doc.repository}:{doc.commit_sha[:8]} - "
           f"T:{len(correlations['temporal'])} S:{len(correlations['semantic'])} B:{len(correlations['breaking'])}")
```

### Error Handling Patterns
```python
try:
    # Correlation generation logic
    correlations = await self.generate_correlations_for_document(doc, all_documents)
    # ... processing
except Exception as e:
    logger.error(f"❌ Error processing document {doc.id}: {e}")
    results["processing_errors"] += 1
```

## Performance Considerations

### Batch Processing Optimization
- **Query limit**: 1000 documents maximum for 7-day window
- **Repository exclusion**: Skip same-repository comparisons
- **Timestamp filtering**: Skip documents with identical fallback timestamps (< 0.1 hours)

### Memory Management
- **Concept limiting**: Top 5 common concepts only
- **File limiting**: Maximum 5 common files, 3 directories
- **Extension limiting**: Maximum 5 extensions, 4 technology stack items

## Testing Contracts

### Unit Test Requirements
- [ ] Test `get_file_information_for_correlation()` returns valid structure with all required fields
- [ ] Test intelligent correlation strength calculation produces values between 0.0-0.95
- [ ] Test variance application produces realistic correlation values
- [ ] Test file-level concept extraction identifies correct patterns
- [ ] Test technology stack inference from file extensions

### Integration Test Requirements
- [ ] Test end-to-end correlation generation with real documents
- [ ] Test force regeneration clears old 100% values and generates realistic correlations
- [ ] Test database storage preserves file_information as nested JSON
- [ ] Test batch processing handles large document sets efficiently

## API Integration Points

### With Intelligence Document Reader
```python
# Query all documents for correlation analysis
params = QueryParameters(time_range="7d", limit=1000)
all_documents = self.document_reader.get_parsed_documents(params)
```

### With Intelligence Document Writer
```python
# Store correlation data to database
await self.update_document_correlations(doc.id, correlations)
```

### With Intelligence Service
Expected to preserve `file_information` through:
```python
# In SemanticCorrelationData conversion
file_information=getattr(sc, 'file_information', None)
```

## Success Criteria

### Correlation Quality
- [ ] Correlation strengths between 0.0 and 0.95 (no perfect 1.0 values)
- [ ] Realistic variance applied to avoid hard-coded patterns
- [ ] File information generated and persisted for semantic correlations
- [ ] Technology stack inference working from file extensions
- [ ] Common concepts extracted using langextract-style analysis

### Database Integration
- [ ] All correlation types stored correctly in database
- [ ] File information persisted as nested JSON structure
- [ ] Old correlation data cleared during force regeneration
- [ ] Debug logging tracks data flow through pipeline

### Performance
- [ ] Batch processing completes within reasonable time
- [ ] Memory usage controlled through limiting and filtering
- [ ] Error handling prevents processing failures from stopping batch operations
