-- ============================================================================
-- Migration: 001_processed_events.sql
-- Description: Idempotency table for Kafka consumer event deduplication
-- Ticket: OMN-1669 (STORE-004)
-- Database: PostgreSQL (omninode_bridge)
--
-- Copyright (c) 2025 OmniNode Team
-- SPDX-License-Identifier: Apache-2.0
-- ============================================================================

-- Idempotency table for Kafka consumer event deduplication
-- This table tracks which events have been processed to prevent duplicate processing
-- Events are retained for 7 days for debugging and auditing purposes

CREATE TABLE IF NOT EXISTS processed_events (
    event_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for retention cleanup (delete events older than 7 days)
-- This index enables efficient cleanup queries:
-- DELETE FROM processed_events WHERE processed_at < NOW() - INTERVAL '7 days'
CREATE INDEX IF NOT EXISTS idx_processed_events_time
ON processed_events(processed_at);

-- Documentation comment
COMMENT ON TABLE processed_events IS 'Kafka consumer idempotency tracking. Events are retained for 7 days.';
COMMENT ON COLUMN processed_events.event_id IS 'Unique identifier of the Kafka event (correlation_id or message_id)';
COMMENT ON COLUMN processed_events.processed_at IS 'Timestamp when the event was successfully processed';
