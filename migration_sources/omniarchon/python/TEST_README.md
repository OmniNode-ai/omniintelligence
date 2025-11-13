# Bridge Intelligence API Test Suite

This directory contains comprehensive tests for the Bridge Intelligence API.

## Test Files

### 1. test_bridge_intelligence_corrected.py ✅ **RECOMMENDED**
**Purpose**: Comprehensive positive test suite for Bridge Intelligence API

**What it tests**:
- Intelligence generation with quality metrics
- Health check endpoints
- Performance consistency across multiple requests
- All intelligence sources (langextract, quality_scorer)

**Requirements**:
- Bridge Intelligence API running on port 8053

**Usage**:
```bash
python3 python/test_bridge_intelligence_corrected.py
```

**Expected Results**: 3/3 tests passing, ~1.65ms average response time

---

### 2. test_bridge_negative_cases.py ✅ **RECOMMENDED**
**Purpose**: Negative test cases and edge case validation

**What it tests**:
- Concurrent request handling (no deadlock)
- Invalid input handling
- Rapid sequential requests
- Connection resilience
- Health check under load

**Requirements**:
- Bridge Intelligence API running on port 8053

**Usage**:
```bash
python3 python/test_bridge_negative_cases.py
```

**Expected Results**: 5/5 tests passing, validates robustness

---

### 3. test_intelligence_stamping.py ⚠️ **REQUIRES EXTERNAL SERVICE**
**Purpose**: Complete integration test including metadata stamping

**What it tests**:
- Intelligence generation (Port 8053)
- Metadata enrichment
- File stamping (Port 8057 - **requires OmniNode Bridge**)
- Complete workflow integration

**Requirements**:
- Bridge Intelligence API running on port 8053 ✅
- OmniNode Bridge Metadata Stamping Service on port 8057 ❌ (not implemented yet)

**Usage**:
```bash
# Note: Will fail on stamping tests without OmniNode Bridge service
python3 python/test_intelligence_stamping.py
```

**Expected Results**:
- Test 1 (intelligence generation): PASS
- Tests 2-4 (stamping): FAIL (requires OmniNode Bridge)

---

## Quick Start

### Run All Recommended Tests
```bash
# Positive tests
python3 python/test_bridge_intelligence_corrected.py

# Negative/edge case tests
python3 python/test_bridge_negative_cases.py
```

### Check Service Health
```bash
# Bridge Intelligence API health
curl http://localhost:8053/api/bridge/health | jq '.'

# Quick intelligence generation test
curl -X POST http://localhost:8053/api/bridge/generate-intelligence \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/test.py","content":"print(1)"}' | jq '.success'
```

---

## Test Coverage Summary

| Category | Test File | Coverage |
|----------|-----------|----------|
| **Positive Tests** | test_bridge_intelligence_corrected.py | ✅ 3 tests |
| **Negative Tests** | test_bridge_negative_cases.py | ✅ 5 tests |
| **Integration Tests** | test_intelligence_stamping.py | ⚠️ Requires OmniNode Bridge |

**Total Core Test Coverage**: 8 tests (all passing)

---

## Test Results Expected

### test_bridge_intelligence_corrected.py
```
✅ Intelligence Generation: 8.23ms (target: <2000ms)
✅ Health Check: 6.48ms
✅ Performance (5 req): 1.65ms avg

ALL TESTS PASSED
```

### test_bridge_negative_cases.py
```
✅ Concurrent Initialization: No deadlock
✅ Invalid Input Handling: Graceful handling
✅ Rapid Sequential Requests: Consistent performance
✅ Connection Resilience: Validated
✅ Health Check Under Load: Remains responsive

ALL NEGATIVE TESTS PASSED
```

---

## Troubleshooting

### Test Failures

**"Connection refused" or "Service unavailable"**
- Ensure Bridge Intelligence API is running: `docker compose ps`
- Check service health: `curl http://localhost:8053/api/bridge/health`

**"Lock timeout" errors**
- Service may be overloaded
- Check logs: `docker compose logs archon-intelligence`
- Restart service: `docker compose restart archon-intelligence`

**Slow performance**
- Check system resources
- Verify database connectivity (optional, for pattern intelligence)
- Review logs for warnings

---

## Performance Benchmarks

**Target**: <2000ms per intelligence generation
**Actual**: ~1.65ms average (99.92% better than target)

**Response Times**:
- Intelligence Generation: 1.28ms - 8.23ms
- Health Check: <10ms
- Under Load: Consistent <50ms

---

## Contributing

When adding new tests:
1. Add positive tests to `test_bridge_intelligence_corrected.py`
2. Add negative/edge cases to `test_bridge_negative_cases.py`
3. Update this README with new test coverage
4. Ensure all tests pass before committing

---

**Last Updated**: 2025-10-07
**Status**: All core tests passing (8/8)
