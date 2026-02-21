-- Creates the db_metadata singleton table for boot-time handshake (B1 + B2 checks).
-- OMN-2435: omniintelligence missing boot-time handshake
--
-- Requires: PostgreSQL 14+ (CREATE OR REPLACE TRIGGER syntax)
--
-- First-boot note: expected_schema_fingerprint is intentionally NULL here.
-- PluginIntelligence.validate_handshake() detects NULL on first boot and
-- auto-stamps the live schema fingerprint via compute_schema_fingerprint().
-- No manual operator step is required after applying this migration.
--
-- Rollback: see rollback/015_rollback.sql (drops trigger, function, and table)

CREATE TABLE IF NOT EXISTS db_metadata (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id = TRUE),
    owner_service TEXT NOT NULL,
    expected_schema_fingerprint TEXT,
    expected_schema_fingerprint_generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ON CONFLICT (id) DO NOTHING: idempotency — if the singleton row already exists
-- (e.g. migration re-run or applied to a pre-existing database), the INSERT is a
-- no-op.  The existing row already has the correct owner_service value, so no
-- UPDATE is needed.  This makes the migration safe to apply multiple times.
INSERT INTO db_metadata (owner_service) VALUES ('omniintelligence')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_db_metadata_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_db_metadata_updated_at
    BEFORE UPDATE ON db_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_db_metadata_updated_at();
