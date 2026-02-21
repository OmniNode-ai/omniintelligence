-- Creates the db_metadata singleton table for boot-time handshake (B1 + B2 checks).
-- OMN-2435: omniintelligence missing boot-time handshake
--
-- First-boot note: expected_schema_fingerprint is intentionally NULL here.
-- PluginIntelligence.validate_handshake() detects NULL on first boot and
-- auto-stamps the live schema fingerprint via compute_schema_fingerprint().
-- No manual operator step is required after applying this migration.

CREATE TABLE IF NOT EXISTS db_metadata (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id = TRUE),
    owner_service TEXT NOT NULL,
    expected_schema_fingerprint TEXT,
    expected_schema_fingerprint_generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO db_metadata (owner_service) VALUES ('omniintelligence')
ON CONFLICT DO NOTHING;
