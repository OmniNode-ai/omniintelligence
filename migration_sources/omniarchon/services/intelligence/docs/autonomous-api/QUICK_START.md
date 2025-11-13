# Track 3 APIs - Quick Start Guide

**5-Minute Guide to Track 3 Autonomous Execution APIs**

## Step 1: Start the Service (30 seconds)

```bash
# Option A: Docker (Recommended)
cd /Volumes/PRO-G40/Code/Archon
docker compose up archon-intelligence -d

# Option B: Local Development
cd services/intelligence
poetry install
poetry run python app.py
```

Verify: http://localhost:8053/api/autonomous/health

## Step 2: Test Agent Prediction (1 minute)

```bash
curl -X POST http://localhost:8053/api/autonomous/predict/agent \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Implement OAuth2 authentication with Google",
    "task_type": "code_generation",
    "complexity": "complex",
    "change_scope": "module"
  }' | jq
```

Expected output:
```json
{
  "recommended_agent": "agent-api-architect",
  "confidence_score": 0.87,
  "confidence_level": "high",
  "reasoning": "Agent has 92% success rate on...",
  "expected_success_rate": 0.92
}
```

## Step 3: Try All Endpoints (3 minutes)

### Time Estimation
```bash
curl -X POST "http://localhost:8053/api/autonomous/predict/time?agent=agent-api-architect" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Implement OAuth2",
    "task_type": "code_generation",
    "complexity": "complex"
  }' | jq '.estimated_duration_ms'
```

### Safety Score
```bash
curl -X POST "http://localhost:8053/api/autonomous/calculate/safety?task_type=code_generation&complexity=0.7&change_scope=module" | jq '{safety_score, can_execute_autonomously}'
```

### Success Patterns
```bash
curl "http://localhost:8053/api/autonomous/patterns/success?min_success_rate=0.8&limit=5" | jq '.[0] | {pattern_name, success_rate, agent_sequence}'
```

### Pattern Ingestion
```bash
curl -X POST http://localhost:8053/api/autonomous/patterns/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "execution_id": "660f9500-f3ac-42e5-b827-557766550111",
    "task_characteristics": {
      "task_description": "Test task",
      "task_type": "code_generation",
      "complexity": "moderate",
      "change_scope": "module"
    },
    "execution_details": {
      "agent_used": "agent-api-architect",
      "start_time": "2025-10-01T10:00:00Z",
      "end_time": "2025-10-01T10:05:00Z",
      "steps_executed": ["analyze", "implement", "test"]
    },
    "outcome": {
      "success": true,
      "duration_ms": 300000,
      "quality_score": 0.89
    }
  }' | jq
```

## Step 4: Python Integration (1 minute)

Create `test_track3.py`:

```python
import asyncio
import httpx

async def test_autonomous_apis():
    base_url = "http://localhost:8053/api/autonomous"

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Test 1: Predict agent
        print("1. Testing agent prediction...")
        response = await client.post(
            f"{base_url}/predict/agent",
            json={
                "task_description": "Implement OAuth2 authentication",
                "task_type": "code_generation",
                "complexity": "complex",
                "change_scope": "module",
            },
        )
        agent = response.json()
        print(f"   ✅ Recommended: {agent['recommended_agent']}")
        print(f"   ✅ Confidence: {agent['confidence_score']:.1%}")

        # Test 2: Time estimation
        print("\n2. Testing time estimation...")
        response = await client.post(
            f"{base_url}/predict/time",
            params={"agent": agent["recommended_agent"]},
            json={
                "task_description": "Implement OAuth2 authentication",
                "task_type": "code_generation",
                "complexity": "complex",
            },
        )
        time_est = response.json()
        print(f"   ✅ Estimated: {time_est['estimated_duration_ms']}ms")
        print(f"   ✅ P95: {time_est['p95_duration_ms']}ms")

        # Test 3: Safety score
        print("\n3. Testing safety assessment...")
        response = await client.post(
            f"{base_url}/calculate/safety",
            params={
                "task_type": "code_generation",
                "complexity": 0.7,
                "change_scope": "module",
            },
        )
        safety = response.json()
        print(f"   ✅ Safety score: {safety['safety_score']:.2f}")
        print(f"   ✅ Can execute autonomously: {safety['can_execute_autonomously']}")

        # Test 4: Get patterns
        print("\n4. Testing pattern retrieval...")
        response = await client.get(
            f"{base_url}/patterns/success",
            params={"min_success_rate": 0.8, "limit": 3},
        )
        patterns = response.json()
        print(f"   ✅ Found {len(patterns)} patterns")
        for p in patterns:
            print(f"      - {p['pattern_name']}: {p['success_rate']:.1%}")

        print("\n✅ All tests passed!")

asyncio.run(test_autonomous_apis())
```

Run it:
```bash
python test_track3.py
```

## Next Steps

1. **Review Full Documentation**:
   - [OpenAPI Specification](./OPENAPI_SPEC.md) - Complete API reference
   - [Integration Guide](./TRACK4_INTEGRATION_GUIDE.md) - Production patterns
   - [README](./README.md) - Comprehensive overview

2. **Explore Interactive Docs**:
   - Swagger UI: http://localhost:8053/docs
   - ReDoc: http://localhost:8053/redoc

3. **Check Service Stats**:
   ```bash
   curl http://localhost:8053/api/autonomous/stats | jq
   ```

4. **Integrate with Track 4**:
   - See [TRACK4_INTEGRATION_GUIDE.md](./TRACK4_INTEGRATION_GUIDE.md)
   - Use provided Python client class
   - Implement recommended patterns

## Troubleshooting

### Service Not Running
```bash
# Check if service is up
curl http://localhost:8053/api/autonomous/health

# Check logs
docker compose logs archon-intelligence -f

# Restart service
docker compose restart archon-intelligence
```

### Import Errors
```bash
# Verify Python path
cd services/intelligence
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Check imports
python -c "from src.api.autonomous.routes import router; print('OK')"
```

### Slow Response Times
```bash
# Check performance
curl -X POST http://localhost:8053/api/autonomous/predict/agent \
  -H "Content-Type: application/json" \
  -d '{"task_description":"test","task_type":"code_generation","complexity":"simple","change_scope":"single_file"}' \
  -w "\nTime: %{time_total}s\n"

# Should be <0.1s (100ms target)
```

## Support

- **Issues**: Check logs first, then consult [README.md](./README.md)
- **Questions**: See [TRACK4_INTEGRATION_GUIDE.md](./TRACK4_INTEGRATION_GUIDE.md)
- **API Docs**: http://localhost:8053/docs

---

**Quick Start Complete** ✅

You now have Track 3 APIs running and tested. Proceed to the Integration Guide for production patterns.
