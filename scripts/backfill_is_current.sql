-- Backfill script: Fix is_current=FALSE on version-1 candidate patterns.
--
-- Root cause: upsert_pattern (dispatch bridge) inserted all patterns with
-- is_current=FALSE regardless of version. This made them invisible to:
--   1. The auto-promote handler (queries WHERE is_current = TRUE)
--   2. The projection snapshot query (queries WHERE is_current = TRUE)
--
-- This script sets is_current=TRUE for all version-1 patterns that were
-- incorrectly inserted with is_current=FALSE. Re-running is safe (idempotent).
--
-- After running this script:
--   1. The promotion scheduler (every 5 min) will find these candidates
--      and promote eligible ones to provisional/validated.
--   2. Run backfill_pattern_projection.py to publish a fresh projection
--      snapshot so omnidash receives updated pattern data.
--
-- Usage:
--   psql $OMNIINTELLIGENCE_DB_URL -f scripts/backfill_is_current.sql
--
-- Related: upsert_pattern fix in learned_patterns.repository.yaml

BEGIN;

-- Step 1: Count affected rows (informational)
SELECT
    count(*) AS affected_count,
    count(*) FILTER (WHERE status = 'candidate') AS candidates,
    count(*) FILTER (WHERE status = 'provisional') AS provisionals,
    count(*) FILTER (WHERE status = 'validated') AS validated
FROM learned_patterns
WHERE is_current = FALSE
  AND version = 1;

-- Step 2: Fix is_current for version-1 patterns
UPDATE learned_patterns
SET is_current = TRUE,
    updated_at = NOW()
WHERE is_current = FALSE
  AND version = 1;

COMMIT;
