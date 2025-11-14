# Database Schema for OmniIntelligence

This directory contains database migrations and schema definitions for the OmniIntelligence project.

## Overview

The OmniIntelligence database schema supports:
- **FSM State Tracking**: Unified state management for all intelligence FSMs
- **State History**: Complete audit trail of all state transitions
- **Workflow Execution**: Tracking of orchestrator workflow executions
- **Distributed Coordination**: Action lease management for distributed systems

## Database Tables

### `fsm_state`

Main table for tracking FSM state across all intelligence operations.

**Columns:**
- `id`: UUID primary key
- `fsm_type`: FSM type (INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT)
- `entity_id`: Unique entity identifier
- `current_state`: Current state in the FSM
- `previous_state`: Previous state
- `transition_timestamp`: Last transition timestamp
- `metadata`: JSONB metadata
- `lease_id`: Action lease ID for distributed coordination
- `lease_epoch`: Lease epoch
- `lease_expires_at`: Lease expiration timestamp

**Constraints:**
- Unique constraint on `(fsm_type, entity_id)`

**Indexes:**
- `idx_fsm_state_fsm_entity`: Query by FSM type and entity
- `idx_fsm_state_current_state`: Query by state
- `idx_fsm_state_type_state`: Query by FSM type and state
- `idx_fsm_state_lease`: Lease management
- `idx_fsm_state_metadata`: JSONB metadata queries

### `fsm_state_history`

Historical record of all FSM state transitions for auditing and analytics.

**Columns:**
- `id`: Bigserial primary key
- `fsm_type`: FSM type
- `entity_id`: Entity identifier
- `from_state`: Previous state
- `to_state`: New state
- `action`: Action that caused transition
- `transitioned_at`: Transition timestamp
- `duration_ms`: Time spent in previous state
- `correlation_id`: Correlation ID for tracing
- `metadata`: JSONB metadata
- `success`: Whether transition succeeded
- `error_message`: Error if failed

**Automatically Populated:**
- Trigger `trigger_record_fsm_history` automatically records transitions from `fsm_state`

### `workflow_executions`

Tracks orchestrator workflow executions.

**Columns:**
- `workflow_id`: Primary key
- `operation_type`: Operation type (DOCUMENT_INGESTION, etc.)
- `entity_id`: Entity being processed
- `status`: Workflow status (RUNNING, COMPLETED, FAILED, PAUSED)
- `current_step`: Current workflow step
- `completed_steps`: JSONB array of completed steps
- `started_at`: Start timestamp
- `completed_at`: Completion timestamp
- `duration_ms`: Execution duration
- `correlation_id`: Correlation ID
- `input_payload`: JSONB input
- `output_results`: JSONB results
- `error_message`: Error if failed
- `retry_count`: Number of retries

## Migrations

Migrations are SQL files in the `migrations/` directory, numbered sequentially.

### Available Migrations

1. **001_create_fsm_state_table.sql**: Create fsm_state table with indexes and triggers
2. **002_create_fsm_state_history.sql**: Create history table with automatic recording
3. **003_create_workflow_executions.sql**: Create workflow execution tracking

### Applying Migrations

Use the migration runner script:

```bash
# Show migration status
python scripts/migration/apply_migrations.py --status

# Apply all pending migrations
python scripts/migration/apply_migrations.py --database-url postgresql://user:pass@host:5432/db

# Or use environment variable
export DATABASE_URL=postgresql://user:pass@host:5432/db
python scripts/migration/apply_migrations.py
```

### Rollback

Rollback scripts are in `migrations/rollback/`:

```bash
psql $DATABASE_URL -f deployment/database/migrations/rollback/001_rollback.sql
```

## Utility Functions

### `cleanup_old_fsm_history(retention_days)`

Clean up old FSM history records:

```sql
SELECT cleanup_old_fsm_history(90);  -- Clean up records older than 90 days
```

### `cleanup_completed_workflows(retention_days)`

Clean up completed workflows:

```sql
SELECT cleanup_completed_workflows(30);  -- Clean up workflows older than 30 days
```

### `find_stuck_workflows(timeout_hours)`

Find workflows stuck in RUNNING state:

```sql
SELECT * FROM find_stuck_workflows(24);  -- Find workflows stuck for 24+ hours
```

## FSM State Management

### FSM Types

- **INGESTION**: Document ingestion (RECEIVED → PROCESSING → INDEXED)
- **PATTERN_LEARNING**: Pattern learning (FOUNDATION → MATCHING → VALIDATION → TRACEABILITY → COMPLETED)
- **QUALITY_ASSESSMENT**: Quality assessment (RAW → ASSESSING → SCORED → STORED)

### State Transitions

All state transitions go through the reducer and are:
1. Validated against FSM definition
2. Recorded in `fsm_state` table
3. Automatically logged in `fsm_state_history`
4. May emit intents to orchestrator

### Lease Management

For distributed coordination, reducers use action leases:

```sql
-- Acquire lease
UPDATE fsm_state
SET lease_id = 'lease_123',
    lease_epoch = 1,
    lease_expires_at = NOW() + INTERVAL '5 minutes'
WHERE fsm_type = 'INGESTION'
  AND entity_id = 'doc_123'
  AND (lease_id IS NULL OR lease_expires_at < NOW());

-- Release lease
UPDATE fsm_state
SET lease_id = NULL,
    lease_epoch = NULL,
    lease_expires_at = NULL
WHERE fsm_type = 'INGESTION'
  AND entity_id = 'doc_123'
  AND lease_id = 'lease_123'
  AND lease_epoch = 1;
```

## Queries

### Get Current State

```sql
SELECT current_state, metadata
FROM fsm_state
WHERE fsm_type = 'INGESTION'
  AND entity_id = 'doc_123';
```

### Get State History

```sql
SELECT from_state, to_state, action, transitioned_at, duration_ms
FROM fsm_state_history
WHERE fsm_type = 'INGESTION'
  AND entity_id = 'doc_123'
ORDER BY transitioned_at DESC;
```

### Get Active Workflows

```sql
SELECT workflow_id, operation_type, current_step, started_at
FROM workflow_executions
WHERE status = 'RUNNING'
ORDER BY started_at DESC;
```

### FSM Statistics

```sql
-- Count entities by state
SELECT current_state, COUNT(*)
FROM fsm_state
WHERE fsm_type = 'INGESTION'
GROUP BY current_state;

-- Average time in each state
SELECT
    to_state,
    AVG(duration_ms) as avg_duration_ms,
    COUNT(*) as transition_count
FROM fsm_state_history
WHERE fsm_type = 'PATTERN_LEARNING'
  AND success = true
  AND transitioned_at > NOW() - INTERVAL '7 days'
GROUP BY to_state;
```

## Maintenance

### Regular Maintenance Tasks

1. **Clean up old history** (weekly):
   ```sql
   SELECT cleanup_old_fsm_history(90);
   ```

2. **Clean up completed workflows** (daily):
   ```sql
   SELECT cleanup_completed_workflows(30);
   ```

3. **Find stuck workflows** (hourly):
   ```sql
   SELECT * FROM find_stuck_workflows(24);
   ```

4. **Vacuum tables** (weekly):
   ```sql
   VACUUM ANALYZE fsm_state;
   VACUUM ANALYZE fsm_state_history;
   VACUUM ANALYZE workflow_executions;
   ```

### Monitoring

Monitor these metrics:
- State distribution across FSMs
- Transition success rate
- Average transition duration
- Stuck workflows
- Lease conflicts
- Table sizes

## Connection Configuration

Set the database URL in your environment:

```bash
export DATABASE_URL=postgresql://username:password@host:5432/omniintelligence
```

Or in Python:

```python
import os
database_url = os.getenv("DATABASE_URL", "postgresql://localhost/omniintelligence")
```

## Troubleshooting

### Lease Conflicts

If you see lease conflicts, check for expired leases:

```sql
SELECT * FROM fsm_state
WHERE lease_expires_at < NOW()
  AND lease_id IS NOT NULL;
```

Clean them up:

```sql
UPDATE fsm_state
SET lease_id = NULL, lease_epoch = NULL, lease_expires_at = NULL
WHERE lease_expires_at < NOW();
```

### Stuck Entities

Find entities stuck in transitional states:

```sql
SELECT fsm_type, entity_id, current_state, transition_timestamp
FROM fsm_state
WHERE current_state IN ('PROCESSING', 'ASSESSING', 'MATCHING')
  AND transition_timestamp < NOW() - INTERVAL '1 hour';
```

## Schema Version

Current schema version: **v1.0.0**

Last updated: **2025-11-14**
