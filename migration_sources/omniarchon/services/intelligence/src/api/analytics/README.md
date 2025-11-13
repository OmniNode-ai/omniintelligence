># Analytics API

FastAPI-based analytics service for traceability and pattern learning system.

## Features

✅ **8 REST Endpoints** for comprehensive analytics
✅ **Mock Data Support** - works without database initially
✅ **Pydantic Models** - full type safety
✅ **Auto-generated OpenAPI** docs
✅ **CORS Enabled** - ready for frontend integration

## API Endpoints

### 1. List Execution Traces
```http
GET /api/analytics/traces
```
**Query Parameters:**
- `limit` (int, default: 50): Max traces to return
- `offset` (int, default: 0): Pagination offset
- `status` (string): Filter by status (completed, in_progress, failed)
- `success` (bool): Filter by success
- `session_id` (UUID): Filter by session

**Response:** Paginated list of traces

### 2. Get Trace Details
```http
GET /api/analytics/traces/{correlation_id}
```
**Returns:** Complete trace with hooks, endpoints, agent routing

### 3. List Success Patterns
```http
GET /api/analytics/patterns
```
**Query Parameters:**
- `limit` (int, default: 20): Max patterns to return
- `offset` (int, default: 0): Pagination offset
- `min_success_rate` (float): Minimum success rate (0.0-1.0)
- `min_usage_count` (int): Minimum usage count
- `domain` (string): Filter by domain

**Response:** Paginated list of learned patterns

### 4. Get Pattern Usage Stats
```http
GET /api/analytics/patterns/{pattern_id}/usage
```
**Returns:** Usage over time, trends, success rates

### 5. Get Agent Effectiveness
```http
GET /api/analytics/agents/effectiveness
```
**Returns:** Performance metrics for all agents

### 6. Get Agent Chaining Patterns
```http
GET /api/analytics/agents/chaining
```
**Returns:** Common multi-agent workflows

### 7. Get Error Analysis
```http
GET /api/analytics/errors
```
**Query Parameters:**
- `time_range` (string): 24h, 7d, 30d
- `error_type` (string): Filter by error type

**Response:** Error patterns with trends

### 8. Get Dashboard Summary
```http
GET /api/analytics/dashboard/summary
```
**Returns:** High-level metrics for dashboard

## Running Locally

### Prerequisites
```bash
pip install fastapi uvicorn faker pydantic
```

### Start Server
```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from analytics import router

app = FastAPI(title="Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8055)
```

```bash
python main.py
```

### Access Docs
- Swagger UI: http://localhost:8055/docs
- ReDoc: http://localhost:8055/redoc

## Mock Data

The API currently uses **200+ realistic mock traces** generated with Faker:
- 11 agent types from actual agent registry
- Realistic timestamps, durations, success rates
- 50 success patterns with vector embeddings (mocked)
- Agent effectiveness metrics
- Error patterns and trends

**Mock data is consistent across requests** (cached on module load)

## Database Integration (Week 4)

When ready to integrate with real database:

1. Create `database.py`:
```python
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)
```

2. Replace mock functions in `routes.py`:
```python
# Before (mock)
traces = get_mock_traces(limit=limit, offset=offset)

# After (database)
result = supabase.table("execution_traces") \
    .select("*") \
    .limit(limit) \
    .offset(offset) \
    .execute()
traces = result.data
```

3. Update health check:
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "analytics-api",
        "mode": "database",  # Changed from "mock_data"
    }
```

## Testing

```bash
# Run tests
pytest services/intelligence/src/api/analytics/tests/

# Test specific endpoint
curl http://localhost:8055/api/analytics/traces

# Test with filters
curl "http://localhost:8055/api/analytics/traces?status=completed&limit=10"

# Get dashboard summary
curl http://localhost:8055/api/analytics/dashboard/summary
```

## Frontend Integration

Example React usage:
```typescript
// Fetch traces
const response = await fetch(
  'http://localhost:8055/api/analytics/traces?limit=20&status=completed'
);
const data = await response.json();

// data.traces contains ExecutionTraceResponse[]
data.traces.forEach(trace => {
  console.log(trace.correlation_id, trace.agent_selected, trace.success);
});
```

## Performance

Current (Mock):
- Average response time: <10ms
- All endpoints: <50ms

Target (Database):
- Average response time: <100ms
- Dashboard summary: <200ms
- Pattern matching: <150ms

## Next Steps

- [ ] Add pytest test suite
- [ ] Integrate with Supabase database (Week 4)
- [ ] Add request validation middleware
- [ ] Implement rate limiting
- [ ] Add caching layer (Redis)
- [ ] Create React dashboard consuming these APIs

## File Structure

```
analytics/
├── __init__.py           # Module exports
├── routes.py             # FastAPI router (8 endpoints)
├── models.py             # Pydantic request/response models
├── mock_data.py          # Mock data generators
├── service.py            # Business logic layer (future)
├── database.py           # Database integration (future)
├── README.md             # This file
└── tests/
    ├── test_routes.py
    └── test_mock_data.py
```

## Related Documentation

- Database Schema: `/services/intelligence/database/schema/README.md`
- System Design: `/docs/TRACEABILITY_AND_PATTERN_LEARNING_SYSTEM_DESIGN.md`
- Build Plan: `/docs/PARALLEL_BUILD_PLAN.md`
