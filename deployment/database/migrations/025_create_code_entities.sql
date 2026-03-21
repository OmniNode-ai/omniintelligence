-- OMN-5709: Create code_entities table for AST-extracted code entity storage.
-- Supports idempotent re-crawling via UNIQUE(source_repo, file_path, name, entity_type).

CREATE TABLE IF NOT EXISTS code_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    source_repo TEXT NOT NULL,
    line_start INT,
    line_end INT,
    bases JSONB DEFAULT '[]',
    methods JSONB DEFAULT '[]',
    decorators JSONB DEFAULT '[]',
    docstring TEXT,
    source_code TEXT,
    confidence FLOAT DEFAULT 1.0,
    classification TEXT,
    embedding_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_repo, file_path, name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_code_entities_repo ON code_entities(source_repo);
CREATE INDEX IF NOT EXISTS idx_code_entities_file ON code_entities(source_repo, file_path);
CREATE INDEX IF NOT EXISTS idx_code_entities_type ON code_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_code_entities_file_hash ON code_entities(file_hash);
