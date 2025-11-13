# Manifest Intelligence Handler Activation Checklist

**Purpose**: Step-by-step guide to activate manifest intelligence routing once the handler is implemented.

## Prerequisites

- [ ] `ManifestIntelligenceHandler` class implemented at:
  - `services/intelligence-consumer/src/handlers/manifest_intelligence_handler.py`
- [ ] Handler has required methods:
  - `__init__(postgres_url: str, kafka_bootstrap: str, qdrant_url: str)`
  - `async execute(correlation_id: str, options: Dict[str, Any]) -> Dict[str, Any]`
- [ ] Unit tests written for handler
- [ ] Integration tests written

## Activation Steps

### Step 1: Add Configuration (if needed)

**File**: `services/intelligence-consumer/src/config.py`

Add to `ConsumerConfig` class if not already present:

```python
# PostgreSQL Configuration (add if missing)
postgres_url: str = Field(
    default="postgresql://postgres:password@192.168.86.200:5436/omninode_bridge",
    description="PostgreSQL connection URL"
)

# Qdrant Configuration (add if missing)
qdrant_url: str = Field(
    default="http://qdrant:6333",
    description="Qdrant vector database URL"
)
```

Or use environment variables from `.env`:
```bash
POSTGRES_URL=postgresql://postgres:password@192.168.86.200:5436/omninode_bridge
QDRANT_URL=http://qdrant:6333
```

### Step 2: Uncomment Import

**File**: `services/intelligence-consumer/src/main.py`
**Line**: 24

Change:
```python
# from .handlers.manifest_intelligence_handler import ManifestIntelligenceHandler
```

To:
```python
from .handlers.manifest_intelligence_handler import ManifestIntelligenceHandler
```

### Step 3: Uncomment Handler Instance

**File**: `services/intelligence-consumer/src/main.py`
**Line**: 60

Change:
```python
# self.manifest_intelligence_handler: Optional[ManifestIntelligenceHandler] = None  # Uncomment when handler is ready
```

To:
```python
self.manifest_intelligence_handler: Optional[ManifestIntelligenceHandler] = None
```

### Step 4: Uncomment Handler Initialization

**File**: `services/intelligence-consumer/src/main.py`
**Lines**: 87-92

Change:
```python
# Initialize manifest intelligence handler (uncomment when handler is ready)
# self.manifest_intelligence_handler = ManifestIntelligenceHandler(
#     postgres_url=self.config.postgres_url,  # Add to config if needed
#     kafka_bootstrap=self.config.kafka_bootstrap_servers,
#     qdrant_url=self.config.qdrant_url,  # Add to config if needed
# )
```

To:
```python
# Initialize manifest intelligence handler
self.manifest_intelligence_handler = ManifestIntelligenceHandler(
    postgres_url=self.config.postgres_url,
    kafka_bootstrap=self.config.kafka_bootstrap_servers,
    qdrant_url=self.config.qdrant_url,
)
```

### Step 5: Uncomment Handler Execution

**File**: `services/intelligence-consumer/src/main.py`
**Lines**: 1119-1170

Replace the entire placeholder section (lines 1119-1183) with:

```python
# Check if handler is initialized
if not self.manifest_intelligence_handler:
    error_msg = "ManifestIntelligenceHandler not initialized"
    log.error("manifest_handler_not_initialized", error=error_msg)
    await self.consumer.publish_manifest_failure(
        correlation_id=correlation_id,
        error=error_msg,
    )
    raise RuntimeError(error_msg)

# Process through manifest intelligence handler
manifest_start_time = time.time()
log.info(
    "calling_manifest_intelligence_handler",
    correlation_id=correlation_id,
    options=options,
)

manifest_result = await self.manifest_intelligence_handler.execute(
    correlation_id=correlation_id,
    options=options,
)

manifest_elapsed_ms = int((time.time() - manifest_start_time) * 1000)

log.info(
    "manifest_intelligence_handler_responded",
    processing_time_ms=manifest_elapsed_ms,
    has_manifest_data=bool(manifest_result.get("manifest_data")),
    has_partial_results=bool(manifest_result.get("partial_results")),
)

# Publish completion event
await self.consumer.publish_manifest_completion(
    correlation_id=correlation_id,
    success=manifest_result.get("success", True),
    manifest_data=manifest_result.get("manifest_data"),
    partial_results=manifest_result.get("partial_results"),
)

# Calculate total processing time
total_elapsed_ms = int((time.time() - start_time) * 1000)

log.info(
    "manifest_intelligence_event_completed_successfully",
    total_processing_time_ms=total_elapsed_ms,
    manifest_processing_time_ms=manifest_elapsed_ms,
    overhead_ms=total_elapsed_ms - manifest_elapsed_ms,
)
```

### Step 6: Update Handlers Package

**File**: `services/intelligence-consumer/src/handlers/__init__.py`

Change:
```python
"""
Handler modules for intelligence consumer service.

This package contains handlers for different types of intelligence requests.
"""

# Placeholder for future handler imports
# Example:
# from .manifest_intelligence_handler import ManifestIntelligenceHandler
#
# __all__ = ["ManifestIntelligenceHandler"]
```

To:
```python
"""
Handler modules for intelligence consumer service.

This package contains handlers for different types of intelligence requests.
"""

from .manifest_intelligence_handler import ManifestIntelligenceHandler

__all__ = ["ManifestIntelligenceHandler"]
```

## Verification Steps

### 1. Code Verification

```bash
# Check for syntax errors
cd /Volumes/PRO-G40/Code/omniarchon
python3 -m py_compile services/intelligence-consumer/src/main.py
python3 -m py_compile services/intelligence-consumer/src/handlers/manifest_intelligence_handler.py
```

### 2. Unit Tests

```bash
# Run handler unit tests
pytest services/intelligence-consumer/tests/handlers/test_manifest_intelligence_handler.py -v
```

### 3. Integration Tests

```bash
# Run consumer integration tests
pytest services/intelligence-consumer/tests/test_manifest_integration.py -v
```

### 4. Service Restart

```bash
# Restart consumer service
docker compose restart archon-intelligence-consumer

# Check logs for successful startup
docker logs -f archon-intelligence-consumer | grep -E "(started|manifest)"
```

Expected log output:
```
consumer_service_started
manifest_intelligence_handler initialized successfully
```

### 5. End-to-End Test

```bash
# 1. Produce test event
kafkacat -P -b 192.168.86.200:29092 \
  -t dev.archon-intelligence.intelligence.manifest.requested.v1 <<EOF
{
  "event_type": "omninode.intelligence.event.manifest_intelligence_requested.v1",
  "correlation_id": "e2e-test-$(date +%s)",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "payload": {
    "options": {
      "repository_path": "/Volumes/PRO-G40/Code/omniarchon",
      "include_quality": true,
      "include_performance": true
    }
  }
}
EOF

# 2. Monitor consumer logs
docker logs -f archon-intelligence-consumer | grep -E "(manifest|correlation)"

# 3. Check for completion event
kafkacat -C -b 192.168.86.200:29092 \
  -t dev.archon-intelligence.intelligence.manifest.completed.v1 \
  -o end -c 1
```

Expected behavior:
- ✅ Consumer receives event
- ✅ Calls ManifestIntelligenceHandler.execute()
- ✅ Handler returns results
- ✅ Completion event published
- ✅ No errors in logs

## Rollback Plan

If issues occur, rollback by:

1. **Comment out the import** (line 24 in main.py)
2. **Comment out handler initialization** (lines 87-92 in main.py)
3. **Restore placeholder code** (lines 1119-1183 in main.py)
4. **Restart service**: `docker compose restart archon-intelligence-consumer`

The service will continue processing other events (enrichment, code-analysis) and will publish "handler not implemented" messages for manifest events.

## Troubleshooting

### Handler Import Error
```
ImportError: cannot import name 'ManifestIntelligenceHandler'
```

**Solution**:
- Verify handler file exists at correct path
- Check handler class is defined and exported
- Verify `__init__.py` includes handler in `__all__`

### Handler Initialization Error
```
manifest_handler_not_initialized
```

**Solution**:
- Check handler initialization code is uncommented
- Verify required config values are set
- Check PostgreSQL/Qdrant connectivity
- Review handler constructor for exceptions

### Event Processing Timeout
```
enrichment_failed: timeout waiting for handler
```

**Solution**:
- Check handler execution time
- Increase `intelligence_timeout` in config
- Review handler for blocking operations
- Check network connectivity to dependencies

## Success Metrics

After activation, monitor:

- **Event Processing Rate**: Should match other event types
- **Success Rate**: >95% for valid requests
- **Processing Time**: <5 seconds for typical manifests
- **Error Rate**: <5%
- **Partial Results Rate**: Monitor for degraded performance

## Post-Activation Tasks

- [ ] Update monitoring dashboards with manifest metrics
- [ ] Document manifest options and response schemas
- [ ] Add manifest examples to documentation
- [ ] Create runbook for common issues
- [ ] Set up alerts for high error rates
- [ ] Performance tuning based on production data

## Quick Activation Script

For convenience, use this script to activate all at once:

```bash
#!/bin/bash
# activate_manifest_handler.sh

set -e

CONSUMER_DIR="/Volumes/PRO-G40/Code/omniarchon/services/intelligence-consumer"

echo "🔧 Activating Manifest Intelligence Handler..."

# Uncomment import
sed -i '' 's|^# from .handlers.manifest_intelligence_handler|from .handlers.manifest_intelligence_handler|' \
  "${CONSUMER_DIR}/src/main.py"

# Uncomment handler instance
sed -i '' 's|^        # self.manifest_intelligence_handler|        self.manifest_intelligence_handler|' \
  "${CONSUMER_DIR}/src/main.py"

# Note: Handler initialization and execution must be manually uncommented due to complexity

echo "✅ Basic activation complete"
echo "⚠️  Manual steps required:"
echo "   1. Uncomment handler initialization (lines 87-92)"
echo "   2. Uncomment handler execution (lines 1119-1170)"
echo "   3. Update handlers/__init__.py"
echo "   4. Run verification tests"
echo "   5. Restart service"
```

## Contact

For questions or issues during activation:
- Check logs: `docker logs -f archon-intelligence-consumer`
- Review integration doc: `MANIFEST_INTEGRATION.md`
- Test with placeholder first before uncommenting
