-- OMN-5676: Part 2 enrichment columns for code_entities
-- Adds deterministic classification, quality scoring, enrichment metadata, and multi-language support.
-- All statements are idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

-- Deterministic classification (OMN-5674) — fast, no LLM
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS deterministic_node_type TEXT;
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS deterministic_confidence FLOAT;
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS deterministic_alternatives JSONB;

-- Quality scoring (OMN-5675) — multi-dimensional
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS quality_score FLOAT;
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS quality_dimensions JSONB;
  -- JSONB: {"complexity": 0.7, "maintainability": 0.8, "documentation": 0.6, ...}

-- Enrichment metadata (config-aware idempotency — Invariant 8)
-- Stored separately from enrichment results so operational state does not pollute domain data.
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS enrichment_metadata JSONB DEFAULT '{}';
  -- JSONB: {"classify": {"config_hash": "abc123", "stage_version": "1.0.0", "completed_at": "..."},
  --         "quality":  {"config_hash": "def456", "stage_version": "1.0.0", "completed_at": "..."}}

-- Multi-language support (OMN-5679)
ALTER TABLE code_entities ADD COLUMN IF NOT EXISTS source_language TEXT DEFAULT 'python';

-- Indexes for new columns
CREATE INDEX IF NOT EXISTS idx_code_entities_det_node_type ON code_entities(deterministic_node_type);
CREATE INDEX IF NOT EXISTS idx_code_entities_quality ON code_entities(quality_score);
CREATE INDEX IF NOT EXISTS idx_code_entities_language ON code_entities(source_language);
