# Quality Trends Snapshots Implementation

**Date**: 2025-10-28
**Task**: Enhance /api/quality-trends endpoint to include snapshots array
**Status**: ✅ Complete
**Correlation ID**: 86e57c28-0af3-4f1f-afda-81d11b877258

## Overview

Enhanced the `/api/quality-trends/project/{project_id}/trend` endpoint to support time-series quality snapshots from the `pattern_quality_metrics` database table. This enables the Pattern Dashboard to visualize quality trends over time.

## Changes Made

### 1. New Service Method (`PatternAnalyticsService`)

**File**: `src/api/pattern_analytics/service.py`

Added `get_quality_trend_with_snapshots()` method:
- Queries `pattern_quality_metrics` table with time-series aggregation
- Groups data by 1-hour intervals for granular snapshots
- Calculates linear regression slope for trend detection
- Returns snapshots array with `timestamp`, `overall_quality`, and `file_count`

**Features**:
- Hourly time-series aggregation
- Project-level quality calculation (AVG across all patterns)
- File count tracking (unique pattern count per time interval)
- Trend detection: "improving", "declining", "stable", or "insufficient_data"
- Graceful handling of missing data

### 2. Enhanced API Route (`quality_trends/routes.py`)

**File**: `src/api/quality_trends/routes.py`

Enhanced `GET /api/quality-trends/project/{project_id}/trend` endpoint:
- Added new `hours` query parameter (preferred for dashboard)
- Maintains backward compatibility with `time_window_days` parameter
- Automatic fallback to in-memory service if database unavailable
- Injects database pool via `initialize_db_pool()` function

**Parameters**:
- `hours` (int, optional): Time window in hours (1-8760, preferred for dashboard)
- `time_window_days` (int, optional): Legacy parameter (1-365, for backward compatibility)
- `project_id` (str, required): Project identifier

### 3. Integration Tests

**File**: `tests/integration/test_api_quality_trends.py`

Added `TestQualityTrendsWithSnapshots` test class with 5 test cases:
- Basic snapshots functionality test
- Snapshots format validation
- Backward compatibility test
- Parameter validation test
- Default project test

## API Usage

### Dashboard Integration

**Endpoint**: `GET /api/quality-trends/project/{project_id}/trend?hours={hours}`

**Example Request**:
```bash
GET /api/quality-trends/project/default/trend?hours=24
```

**Example Response**:
```json
{
  "success": true,
  "project_id": "default",
  "trend": "improving",
  "avg_quality": 0.88,
  "snapshots_count": 24,
  "snapshots": [
    {
      "timestamp": "2025-10-28T10:00:00Z",
      "overall_quality": 0.92,
      "file_count": 15
    },
    {
      "timestamp": "2025-10-28T11:00:00Z",
      "overall_quality": 0.89,
      "file_count": 14
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful queries |
| `project_id` | string | Project identifier from request |
| `trend` | string | Trend direction: "improving", "declining", "stable", "insufficient_data" |
| `avg_quality` | float | Average quality score across time window (0.0-1.0) |
| `snapshots_count` | integer | Number of hourly snapshots |
| `snapshots` | array | Time-series data points (see below) |

**Snapshot Object**:
```json
{
  "timestamp": "2025-10-28T10:00:00Z",   // ISO 8601 format
  "overall_quality": 0.92,                // Average quality (0.0-1.0)
  "file_count": 15                        // Unique patterns measured
}
```

### Backward Compatibility

Existing usage with `time_window_days` parameter continues to work:
```bash
GET /api/quality-trends/project/default/trend?time_window_days=30
```
Returns in-memory trend data without snapshots array.

## Database Schema

### pattern_quality_metrics Table

The endpoint queries this table (created in migration 004):

```sql
CREATE TABLE pattern_quality_metrics (
    id UUID PRIMARY KEY,
    pattern_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id),
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    measurement_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    version VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Indexes**:
- `idx_pqm_pattern_id` - Pattern filtering
- `idx_pqm_measurement_timestamp` - Time-series queries
- `idx_pqm_pattern_measurement` - Composite index for pattern + time queries

### Query Pattern

The service uses a CTE-based query:
1. **time_series CTE**: Aggregates metrics by hour with AVG quality and COUNT patterns
2. **trend_calc CTE**: Calculates linear regression slope across time series
3. **Final SELECT**: Combines snapshots with trend metrics

**Project Filtering**:
- Filters by `pattern_lineage_nodes.metadata->>'project_id'`
- Falls back to `'default'` project for unspecified project_id

## Setup Requirements

### Database Pool Initialization

The route requires database pool initialization. Add to `app.py` startup:

```python
from src.api.quality_trends.routes import initialize_db_pool as init_quality_trends_db

# During startup, after db_pool creation
if db_pool:
    init_quality_trends_db(db_pool)
```

### Environment Variables

Required (from `.env`):
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5436
POSTGRES_DATABASE=omninode_bridge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=omninode-bridge-postgres-dev-2024
```

## Testing

### Unit Tests

Tests are in `tests/integration/test_api_quality_trends.py`:

```bash
# Run all quality trends tests
pytest tests/integration/test_api_quality_trends.py -v

# Run only snapshots tests
pytest tests/integration/test_api_quality_trends.py::TestQualityTrendsWithSnapshots -v
```

### Manual Testing

1. **Record Quality Metrics** (if database is empty):
```bash
# Insert sample data via record_quality_metric endpoint or directly to DB
INSERT INTO pattern_quality_metrics (pattern_id, quality_score, confidence, measurement_timestamp)
SELECT id, 0.85, 0.90, NOW() - INTERVAL '1 hour' * generate_series(0, 24)
FROM pattern_lineage_nodes LIMIT 10;
```

2. **Test Endpoint**:
```bash
curl -X GET "http://localhost:8053/api/quality-trends/project/default/trend?hours=24"
```

3. **Verify Response**:
- `success: true`
- `snapshots` array present
- Each snapshot has `timestamp`, `overall_quality`, `file_count`

## Dashboard Integration Checklist

- [ ] Update dashboard to use `hours` parameter instead of `time_window_days`
- [ ] Parse `snapshots` array for time-series visualization
- [ ] Handle `insufficient_data` trend gracefully (empty snapshots array)
- [ ] Use `project_id="default"` for aggregated view across all patterns
- [ ] Display `file_count` to show measurement sample size
- [ ] Implement chart with `timestamp` on X-axis, `overall_quality` on Y-axis

## Performance Characteristics

**Expected Query Time**: <500ms
- Database query: ~200-300ms (with indexes)
- Result aggregation: ~50-100ms
- Network overhead: ~50-100ms

**Scaling Considerations**:
- Query performance scales with time window (hours parameter)
- Recommended maximum: 168 hours (1 week) for optimal performance
- For longer periods, consider daily aggregation instead of hourly

## Fallback Behavior

If database unavailable or query fails:
1. Logs warning: "Database query failed, falling back to in-memory"
2. Uses `QualityHistoryService` (in-memory)
3. Returns trend data without snapshots array
4. Still returns HTTP 200 with basic trend information

## Future Enhancements

1. **Caching**: Add Redis caching for frequently accessed time windows
2. **Aggregation Levels**: Support daily/weekly aggregation for longer time periods
3. **Multi-Project**: Support querying multiple projects in single request
4. **Filtering**: Add pattern type filtering (e.g., only code patterns)
5. **Percentiles**: Include min/max quality in snapshots for variance visualization

## Files Modified

1. `src/api/pattern_analytics/service.py` - Added `get_quality_trend_with_snapshots()` method
2. `src/api/quality_trends/routes.py` - Enhanced endpoint with snapshots support
3. `tests/integration/test_api_quality_trends.py` - Added comprehensive test suite

## Validation

✅ Service method implemented with database queries
✅ API route enhanced with backward compatibility
✅ Integration tests written (5 test cases)
✅ Response schema matches dashboard requirements
✅ Graceful fallback to in-memory service
✅ Documentation complete

## Notes

- Database pool injection required via `initialize_db_pool()` call in `app.py`
- Tests require Docker environment with `omnibase_core` dependencies installed
- Project filtering uses JSONB metadata field: `metadata->>'project_id'`
- Default project (`'default'`) aggregates all patterns regardless of project_id

## Contact

For questions or issues with this implementation:
- Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
- Working Directory: `/Volumes/PRO-G40/Code/Omniarchon/services/intelligence`
