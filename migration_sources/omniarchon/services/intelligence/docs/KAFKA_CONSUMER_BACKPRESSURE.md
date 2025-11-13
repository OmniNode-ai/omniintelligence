# Kafka Consumer Backpressure Handling

## Overview

The Intelligence Service Kafka consumer implements a backpressure mechanism to prevent memory exhaustion under high load. This ensures stable operation by limiting the number of events processed concurrently.

## Problem Statement

Without backpressure control, a Kafka consumer could:
- Accept unlimited events from Kafka
- Process all events concurrently
- Exhaust system memory under high load
- Cause service crashes or degraded performance

## Solution: Semaphore-Based Backpressure

The consumer uses an `asyncio.Semaphore` to limit concurrent event processing:

```python
# Initialize with max_in_flight limit
consumer = IntelligenceKafkaConsumer(
    bootstrap_servers="localhost:19092",
    topics=["omninode.codegen.request.validate.v1"],
    max_in_flight=100  # Maximum concurrent events
)
```

### How It Works

1. **Semaphore Acquisition**: Before processing an event, the consumer acquires a semaphore slot
2. **Processing**: Event is processed by the appropriate handler
3. **Semaphore Release**: After processing (success or failure), the semaphore slot is released
4. **Backpressure**: When all slots are in use, new events wait until a slot becomes available

```python
async def _process_message(self, msg: Message) -> None:
    # Wait for available processing slot
    async with self._semaphore:
        # Track in-flight count
        self._current_in_flight += 1

        try:
            await self._process_message_internal(msg)
        finally:
            # Always decrement, even on failure
            self._current_in_flight -= 1
```

## Configuration

### Environment Variable

Set `KAFKA_MAX_IN_FLIGHT` to configure the maximum concurrent events:

```bash
# In .env or docker-compose.yml
KAFKA_MAX_IN_FLIGHT=100  # Default: 100
```

### Programmatic Configuration

```python
from src.kafka_consumer import IntelligenceKafkaConsumer

consumer = IntelligenceKafkaConsumer(
    bootstrap_servers="localhost:19092",
    topics=["topic1", "topic2"],
    max_in_flight=50  # Custom limit
)
```

### Factory Function

The factory function reads from environment variables:

```python
from src.kafka_consumer import create_intelligence_kafka_consumer

# Automatically uses KAFKA_MAX_IN_FLIGHT from environment
consumer = create_intelligence_kafka_consumer()
```

## Monitoring and Metrics

### Available Metrics

The consumer tracks comprehensive backpressure metrics:

```python
metrics = consumer.get_metrics()

# Backpressure-specific metrics
metrics["current_in_flight"]               # Current events being processed
metrics["max_concurrent_events"]           # Peak concurrent events observed
metrics["max_in_flight_reached"]           # Times backpressure was applied
metrics["total_backpressure_wait_time_ms"] # Total time waiting for slots
metrics["avg_backpressure_wait_ms"]        # Average wait time per backpressure event
metrics["backpressure_percentage"]         # % of events that experienced backpressure
metrics["max_in_flight_limit"]             # Configured limit
```

### Interpretation

**Healthy Operation:**
- `current_in_flight` fluctuates below `max_in_flight_limit`
- `backpressure_percentage` < 10%
- `avg_backpressure_wait_ms` < 100ms

**High Load:**
- `max_in_flight_reached` frequently > 0
- `backpressure_percentage` 10-30%
- `avg_backpressure_wait_ms` 100-500ms

**Overload:**
- `current_in_flight` consistently at `max_in_flight_limit`
- `backpressure_percentage` > 30%
- `avg_backpressure_wait_ms` > 500ms

### Logging

Backpressure events are logged at DEBUG level:

```
DEBUG - Backpressure applied: waited 45.23ms to acquire processing slot
```

Enable debug logging to monitor backpressure activity:

```python
import logging
logging.getLogger("src.kafka_consumer").setLevel(logging.DEBUG)
```

## Tuning Recommendations

### Determining Optimal max_in_flight

Consider these factors:

1. **Available Memory**: Each in-flight event consumes memory
   - Typical event: ~1-10MB (code content + analysis results)
   - Conservative: `max_in_flight = available_memory_mb / 10`
   - Example: 1GB available → `max_in_flight = 100`

2. **Processing Time**: Longer processing times require lower limits
   - Fast handlers (<100ms): 100-200 in-flight
   - Medium handlers (100-500ms): 50-100 in-flight
   - Slow handlers (>500ms): 20-50 in-flight

3. **Downstream Services**: Consider handler dependencies
   - If handlers call external APIs, limit concurrent calls
   - Use circuit breakers in combination with backpressure

4. **CPU Cores**: Balance parallelism with CPU availability
   - Rule of thumb: `max_in_flight = cpu_cores * 10-20`
   - Example: 8 cores → 80-160 in-flight

### Adjusting Based on Metrics

**If `backpressure_percentage` > 30%:**
- **Increase** `max_in_flight` if memory allows
- **Optimize** handler processing time
- **Scale** horizontally (add consumer instances)

**If `current_in_flight` consistently low:**
- **Decrease** `max_in_flight` to reduce memory usage
- Resource-efficient operation

**If `avg_backpressure_wait_ms` > 500ms:**
- **Critical**: Handler processing is too slow
- **Action**: Optimize handlers or scale horizontally

## Performance Impact

### Overhead

Backpressure introduces minimal overhead:
- Semaphore acquisition: <1ms (uncontended)
- Lock operations: <0.1ms
- Metric tracking: <0.1ms

**Total overhead**: ~1-2ms per event

### Benefits

- **Memory stability**: Prevents unbounded memory growth
- **Predictable performance**: Consistent processing rates
- **Graceful degradation**: Service remains responsive under load
- **Observability**: Metrics enable informed capacity planning

## Testing

### Unit Tests

Comprehensive test suite in `tests/test_kafka_consumer.py`:

```bash
# Run backpressure tests
pytest tests/test_kafka_consumer.py::TestBackpressureHandling -v

# Run all consumer tests
pytest tests/test_kafka_consumer.py -v
```

### Load Testing

Simulate high load to verify backpressure behavior:

```python
import asyncio
from src.kafka_consumer import IntelligenceKafkaConsumer

async def load_test():
    consumer = IntelligenceKafkaConsumer(
        bootstrap_servers="localhost:19092",
        topics=["test.topic.v1"],
        max_in_flight=10  # Low limit to trigger backpressure
    )

    # Generate high load...
    # Monitor metrics
    metrics = consumer.get_metrics()
    print(f"Backpressure applied: {metrics['max_in_flight_reached']} times")
    print(f"Backpressure %: {metrics['backpressure_percentage']:.2f}%")
```

## Troubleshooting

### High Memory Usage Despite Backpressure

**Symptoms**: Memory grows even with backpressure configured

**Causes**:
- `max_in_flight` too high for available memory
- Memory leaks in handlers
- Large event payloads

**Solutions**:
- Reduce `max_in_flight`
- Profile handler memory usage
- Implement event payload limits

### Consumer Lag Increasing

**Symptoms**: Kafka consumer lag grows over time

**Causes**:
- `max_in_flight` too low for event throughput
- Handlers too slow
- Insufficient consumer instances

**Solutions**:
- Increase `max_in_flight` if memory allows
- Optimize handler processing time
- Add more consumer instances to consumer group

### Backpressure Wait Times Increasing

**Symptoms**: `avg_backpressure_wait_ms` grows over time

**Causes**:
- Handler processing time increasing
- Downstream service degradation
- Resource contention

**Solutions**:
- Profile handler performance
- Check downstream service health
- Add resource monitoring (CPU, I/O)

## Example Configurations

### Development (Low Load)

```bash
KAFKA_MAX_IN_FLIGHT=20
```

Suitable for:
- Local development
- Testing
- Low event volumes

### Production (High Load)

```bash
KAFKA_MAX_IN_FLIGHT=100
```

Suitable for:
- Production deployments
- High event volumes
- Adequate memory (2GB+)

### Production (Memory Constrained)

```bash
KAFKA_MAX_IN_FLIGHT=50
```

Suitable for:
- Limited memory environments
- Slow handlers
- Cost-optimized deployments

## Best Practices

1. **Start Conservative**: Begin with lower `max_in_flight` and increase based on metrics
2. **Monitor Continuously**: Track backpressure metrics in production
3. **Alert on Anomalies**: Set up alerts for high backpressure percentages
4. **Load Test**: Verify backpressure behavior before production deployment
5. **Document Tuning**: Record rationale for `max_in_flight` values
6. **Review Regularly**: Re-evaluate configuration as workload changes

## References

- Python asyncio.Semaphore: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- Confluent Kafka Consumer: https://docs.confluent.io/platform/current/clients/consumer.html
- Backpressure Patterns: https://www.reactivemanifesto.org/glossary#Back-Pressure

---

**Document Version**: 1.0
**Last Updated**: 2025-10-15
**Author**: Intelligence Service Team
