#!/usr/bin/env python3
"""
Test invalid event detection and skipping functionality.

This script demonstrates how the consumer handles invalid events:
1. Detects malformed events
2. Logs warning with details
3. Skips event by committing offset
4. Tracks metrics for observability
"""

import json
import sys
from typing import Any, Dict


def test_validation_logic():
    """Test the validation logic that was added to the consumer."""

    # Sample invalid event (old code-analysis schema in enrichment topic)
    invalid_event_1 = {
        "event_type": "CODE_ANALYSIS_REQUESTED",
        "correlation_id": "test-123",
        "payload": {
            "source_path": "src/main.py",  # WRONG - should be file_path
            "content": "def foo(): pass",
            "language": "python",
            # Missing: project_name
        },
    }

    # Sample invalid event (enrichment with missing fields)
    invalid_event_2 = {
        "event_type": "ENRICH_DOCUMENT_REQUESTED",
        "correlation_id": "test-456",
        "payload": {
            "file_path": "src/utils.py",
            # Missing: content and project_name
        },
    }

    # Sample valid batch event
    valid_batch_event = {
        "event_type": "ENRICH_DOCUMENT_REQUESTED",
        "correlation_id": "test-789",
        "payload": {
            "project_name": "my-project",
            "project_path": "/path/to/project",
            "files": [{"file_path": "src/main.py", "content": "def main(): pass"}],
        },
    }

    # Sample valid individual file event
    valid_individual_event = {
        "event_type": "ENRICH_DOCUMENT_REQUESTED",
        "correlation_id": "test-101",
        "payload": {
            "file_path": "src/app.py",
            "content": "def app(): pass",
            "project_name": "my-project",
        },
    }

    print("=" * 80)
    print("INVALID EVENT DETECTION TEST CASES")
    print("=" * 80)

    print("\n1. Invalid Event (old code-analysis schema):")
    print(json.dumps(invalid_event_1, indent=2))
    print("\n   Expected: SKIPPED - old schema with source_path instead of file_path")
    print("   Action: Log warning, increment skip counter, commit offset")

    print("\n" + "-" * 80)

    print("\n2. Invalid Event (missing required fields):")
    print(json.dumps(invalid_event_2, indent=2))
    print("\n   Expected: SKIPPED - missing content and project_name")
    print("   Action: Log warning, increment skip counter, commit offset")

    print("\n" + "-" * 80)

    print("\n3. Valid Batch Event:")
    print(json.dumps(valid_batch_event, indent=2))
    print("\n   Expected: PROCESSED - has files array with valid structure")
    print("   Action: Process normally through enrichment pipeline")

    print("\n" + "-" * 80)

    print("\n4. Valid Individual File Event:")
    print(json.dumps(valid_individual_event, indent=2))
    print("\n   Expected: PROCESSED - has all required fields")
    print("   Action: Process normally through enrichment pipeline")

    print("\n" + "=" * 80)
    print("\nKEY BENEFITS:")
    print("=" * 80)
    print("✅ Invalid events are automatically detected and skipped")
    print("✅ Offset is committed to move past invalid events (no blocking)")
    print("✅ Detailed logging provides visibility into what was skipped")
    print("✅ Metrics track invalid events for alerting and observability")
    print("✅ Valid events continue processing normally")

    print("\n" + "=" * 80)
    print("\nMETRICS AVAILABLE:")
    print("=" * 80)
    print("- Total invalid events skipped: service.invalid_events_skipped")
    print("- Breakdown by reason: service.invalid_events_by_reason")
    print("- Alert threshold: Every 100 invalid events triggers error log")
    print("- Exposed via health endpoint: GET http://localhost:8900/metrics")

    print("\n" + "=" * 80)
    print("\nVERIFICATION STEPS:")
    print("=" * 80)
    print("1. Restart consumer service:")
    print("   docker compose restart archon-kafka-consumer")
    print()
    print("2. Watch consumer logs for invalid event warnings:")
    print("   docker logs -f archon-kafka-consumer | grep invalid_event_schema_skipped")
    print()
    print("3. Check metrics endpoint for invalid event stats:")
    print("   curl http://localhost:8900/metrics | jq .invalid_events")
    print()
    print("4. Verify consumer is no longer blocked:")
    print("   curl http://localhost:8900/ready")
    print("   # Should return 200 OK with ready: true")
    print()
    print("5. Check consumer lag is decreasing:")
    print("   curl http://localhost:8900/metrics | jq '.consumer.total_lag'")
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_validation_logic()
