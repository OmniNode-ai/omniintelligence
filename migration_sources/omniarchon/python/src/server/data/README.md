# Intelligence Data Access Layer

This module provides a clean, testable data access layer for intelligence operations, separated from presentation and API concerns.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Clean Architecture Layers                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Presentation   │   Application   │        Data Access          │
│     Layer       │     Layer       │           Layer             │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • API Routes    │ • Intelligence  │ • intelligence_data_access  │
│ • WebSocket     │   Service       │ • Raw data operations       │
│   Handlers      │ • Pydantic      │ • Framework-agnostic        │
│ • HTTP Response │   Models        │ • Independently testable    │
│   Formatting    │ • API Response  │ • Pure data structures      │
│                 │   Conversion    │                             │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Key Benefits

### 🧪 **Testable Data Access**
- **Independent Testing**: Test data operations without API/UI dependencies
- **Data Quality Validation**: Verify data consistency across different content formats
- **Mock-Friendly**: Easy to mock for unit testing
- **Integration Testing**: Test real database operations in isolation

### 🔄 **Clean Separation of Concerns**
- **Data Layer**: Pure data access and parsing logic
- **Service Layer**: API response formatting and presentation concerns
- **Framework Agnostic**: No HTTP or web framework dependencies

### 📊 **Consistent Data Structures**
- **Typed Data Classes**: Strong typing for all data structures
- **Format Normalization**: Handle multiple content formats consistently
- **Validation**: Built-in data validation and error handling

## Usage Examples

### Basic Usage

```python
from server.data.intelligence_data_access import (
    create_intelligence_data_access,
    QueryParameters
)
from server.services.client_manager import get_database_client

# Create data access instance
client = get_database_client()
data_access = create_intelligence_data_access(client)

# Query parameters
params = QueryParameters(
    repository="Archon",
    time_range="24h",
    limit=50
)

# Get raw documents
raw_result = data_access.get_raw_documents(params)
print(f"Found {len(raw_result['documents'])} raw documents")

# Get parsed documents with structured data
parsed_docs = data_access.get_parsed_documents(params)
for doc in parsed_docs:
    print(f"Repository: {doc.repository}")
    print(f"Commit: {doc.commit_sha}")
    if doc.diff_analysis:
        print(f"Changes: {doc.diff_analysis.total_changes}")
    print(f"Correlations: {len(doc.temporal_correlations)}")

# Calculate statistics
stats = data_access.calculate_statistics(params)
print(f"Total changes: {stats.total_changes}")
print(f"Average correlation strength: {stats.average_correlation_strength}")
```

### Testing Data Quality

```python
# Test different content formats
content_formats = [
    # MCP format
    {
        "metadata": {"repository": "test-repo"},
        "code_changes_analysis": {"changed_files": ["file1.py"]}
    },
    # Legacy format  
    {
        "diff_analysis": {"total_changes": 1, "modified_files": ["file1.py"]}
    }
]

for content in content_formats:
    diff_analysis = data_access.parse_diff_analysis(content)
    assert diff_analysis is not None
    assert diff_analysis.total_changes >= 1
```

### Background Services

```python
class IntelligenceBackgroundService:
    def __init__(self):
        client = get_database_client()
        self.data_access = create_intelligence_data_access(client)

    def daily_quality_check(self):
        """Daily data quality validation."""
        params = QueryParameters(time_range="24h", limit=1000)

        # Get all documents from last 24h
        documents = self.data_access.get_parsed_documents(params)

        # Validate data quality
        issues = []
        for doc in documents:
            if not doc.repository or doc.repository == "unknown":
                issues.append(f"Document {doc.id}: Missing repository")

            if not doc.commit_sha or doc.commit_sha == "unknown":
                issues.append(f"Document {doc.id}: Missing commit SHA")

        return {
            "documents_checked": len(documents),
            "issues_found": len(issues),
            "issues": issues
        }
```

## Data Structures

### Core Data Classes

```python
@dataclass
class DiffAnalysisData:
    """Raw diff analysis data."""
    total_changes: int
    added_lines: int
    removed_lines: int
    modified_files: List[str]

@dataclass
class TemporalCorrelationData:
    """Raw temporal correlation data."""
    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float

@dataclass
class IntelligenceDocumentData:
    """Complete intelligence document with all parsed data."""
    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    diff_analysis: Optional[DiffAnalysisData]
    temporal_correlations: List[TemporalCorrelationData]
    semantic_correlations: List[SemanticCorrelationData]
    breaking_changes: List[BreakingChangeData]
    security_analysis: Optional[SecurityAnalysisData]
    raw_content: Dict[str, Any]  # Original content for debugging

@dataclass
class IntelligenceStatsData:
    """Raw statistics data for analysis."""
    total_changes: int
    total_correlations: int
    average_correlation_strength: float
    breaking_changes: int
    repositories_active: int
    correlation_strengths: List[float]  # Raw data for further analysis
    repositories_list: List[str]
```

### Query Parameters

```python
@dataclass
class QueryParameters:
    """Query parameters for data access operations."""
    repository: Optional[str] = None
    time_range: str = "24h"
    limit: int = 50
    offset: int = 0
```

## Content Format Support

The data access layer handles multiple content formats consistently:

### MCP Format (v3.0+)
```json
{
  "metadata": {
    "repository": "repo-name",
    "commit": "abc123",
    "author": "user@example.com"
  },
  "code_changes_analysis": {
    "changed_files": ["file1.py", "file2.js"]
  },
  "cross_repository_correlation": {
    "temporal_correlations": [
      {
        "repository": "related-repo",
        "commit": "def456",
        "time_window": "6h",
        "correlation_strength": "high"
      }
    ]
  }
}
```

### Legacy Git Hook Format
```json
{
  "diff_analysis": {
    "total_changes": 5,
    "added_lines": 100,
    "removed_lines": 50,
    "modified_files": ["file1.py", "file2.js"]
  },
  "correlation_analysis": {
    "temporal_correlations": [
      {
        "repository": "related-repo",
        "commit_sha": "def456",
        "time_diff_hours": 6.0,
        "correlation_strength": 0.9
      }
    ]
  }
}
```

### Project Document Format
```json
{
  "quality_baseline": {
    "code_quality_metrics": {
      "anti_patterns_found": 0,
      "architectural_compliance": "High"
    }
  },
  "repository_info": {
    "repository": "project-repo",
    "commit": "ghi789"
  }
}
```

## Testing

### Unit Tests

```bash
# Run unit tests
cd python
python -m pytest tests/test_intelligence_data_access.py -v

# Run specific test class
python -m pytest tests/test_intelligence_data_access.py::TestIntelligenceDataAccess -v

# Run with coverage
python -m pytest tests/test_intelligence_data_access.py --cov=src.server.data.intelligence_data_access
```

### Data Quality Validation

```bash
# Run comprehensive data quality validation
python scripts/test_intelligence_data_quality.py

# Validate specific repository
python scripts/test_intelligence_data_quality.py --repository Archon

# Validate longer time range
python scripts/test_intelligence_data_quality.py --time-range 7d

# Quiet mode for automated testing
python scripts/test_intelligence_data_quality.py --quiet
echo $?  # Exit code: 0 = success, 1 = failure
```

### Example Test Cases

```python
def test_data_consistency_across_formats():
    """Verify data parsing consistency across different formats."""
    data_access = IntelligenceDataAccess(mock_client)

    # Test same logical data in different formats
    mcp_content = {
        "code_changes_analysis": {"changed_files": ["a.py", "b.py"]}
    }
    legacy_content = {
        "diff_analysis": {"modified_files": ["a.py", "b.py"]}
    }

    mcp_result = data_access.parse_diff_analysis(mcp_content)
    legacy_result = data_access.parse_diff_analysis(legacy_content)

    assert mcp_result.modified_files == legacy_result.modified_files

def test_malformed_data_handling():
    """Verify graceful handling of malformed data."""
    data_access = IntelligenceDataAccess(mock_client)

    malformed_content = {
        "correlation_analysis": {
            "temporal_correlations": [
                {"repository": "repo1"}  # Missing required fields
            ]
        }
    }

    temporal, _, _ = data_access.parse_correlations(malformed_content)
    assert len(temporal) == 1
    assert temporal[0].repository == "repo1"
    assert temporal[0].commit_sha == ""  # Default value
```

## Integration with Existing Code

The new data access layer is designed to be backward compatible:

### Existing Service Layer (Preserved)
```python
# intelligence_service.py now uses data access layer internally
from ..data.intelligence_data_access import create_intelligence_data_access

async def get_intelligence_documents():
    """API endpoint function - uses data access layer."""
    data_access = get_intelligence_data_access()
    documents_data = data_access.get_parsed_documents(params)

    # Convert to API response format
    return IntelligenceResponse(
        documents=[convert_to_api_model(doc) for doc in documents_data]
    )
```

### Direct Data Access (New)
```python
# For background services, CLI tools, etc.
from server.data.intelligence_data_access import create_intelligence_data_access

def background_task():
    """Background task using data access directly."""
    data_access = create_intelligence_data_access(get_database_client())
    stats = data_access.calculate_statistics(QueryParameters(time_range="7d"))

    # Process raw statistics data
    if stats.average_correlation_strength > 0.8:
        send_alert("High correlation detected")
```

## Error Handling

The data access layer provides consistent error handling:

```python
try:
    documents = data_access.get_parsed_documents(params)
except Exception as e:
    logger.error(f"Data access error: {e}")
    # Handle gracefully - return empty results
    documents = []

# Individual parsing methods handle errors gracefully
diff_analysis = data_access.parse_diff_analysis(malformed_content)
# Returns None for invalid data, never raises exceptions
```

## Performance Considerations

- **Batch Operations**: Use appropriate limit/offset for large datasets
- **Time Range Filtering**: Apply time filters to reduce data processing
- **Repository Filtering**: Filter by repository to reduce query scope
- **Caching**: Data access layer supports caching at higher levels

```python
# Efficient pagination
params = QueryParameters(limit=100, offset=0)
while True:
    documents = data_access.get_parsed_documents(params)
    if not documents:
        break

    process_documents(documents)
    params.offset += params.limit

# Repository-specific queries
archon_params = QueryParameters(repository="Archon", time_range="7d")
archon_stats = data_access.calculate_statistics(archon_params)
```

## Migration Guide

### From Direct Database Queries
```python
# Before: Direct database access
client = get_database_client()
result = client.table("archon_projects").select("docs").execute()
# Manual parsing and filtering...

# After: Use data access layer  
data_access = create_intelligence_data_access(client)
documents = data_access.get_parsed_documents(QueryParameters())
```

### From Service Layer
```python
# Before: Using service layer for data access
from services.intelligence_service import get_intelligence_documents_from_db
raw_docs = await get_intelligence_documents_from_db()

# After: Direct data access (if you don't need API formatting)
from data.intelligence_data_access import create_intelligence_data_access  
data_access = create_intelligence_data_access(get_database_client())
parsed_docs = data_access.get_parsed_documents(QueryParameters())
```

## Future Enhancements

1. **Caching Layer**: Add caching support for frequently accessed data
2. **Async Support**: Add async versions of data access methods
3. **Query Builder**: More sophisticated query building capabilities
4. **Data Validation**: Enhanced data validation and schema checking
5. **Performance Metrics**: Built-in performance monitoring
6. **Data Export**: Export capabilities for external analysis

## Contributing

When adding new intelligence data types:

1. **Add Data Structure**: Create new dataclass in `intelligence_data_access.py`
2. **Add Parser**: Add parsing method to `IntelligenceDataAccess` class
3. **Add Tests**: Add test cases to `test_intelligence_data_access.py`
4. **Update Service**: Update service layer conversion functions
5. **Update Documentation**: Document the new format support

Example:
```python
@dataclass
class NewAnalysisData:
    """New analysis data structure."""
    metric_value: float
    analysis_type: str

class IntelligenceDataAccess:
    def parse_new_analysis(self, content: Dict[str, Any]) -> Optional[NewAnalysisData]:
        """Parse new analysis data from content."""
        if "new_analysis" in content:
            data = content["new_analysis"]
            return NewAnalysisData(
                metric_value=data.get("metric_value", 0.0),
                analysis_type=data.get("analysis_type", "unknown")
            )
        return None
```
