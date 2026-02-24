-- Migration: 016_create_review_pairing_tables
-- Description: Create five tables for the Review-Fix Pairing and Pattern Reinforcement system
-- Author: omniintelligence
-- Date: 2026-02-24
-- Ticket: OMN-2535
--
-- Creates the following tables:
--   review_findings       — captured review findings from linters/CI/GitHub Checks
--   review_fixes          — fix commits applied for known findings
--   finding_fix_pairs     — confidence-scored pairing of finding + fix
--   pattern_candidates    — candidate fix patterns before promotion
--   pattern_lifecycle     — lifecycle state machine for promoted patterns
--
-- All tables use gen_random_uuid() for primary keys (requires pgcrypto / pg ≥ 13).
-- Rollback: deployment/database/migrations/rollback/016_rollback.sql
--
-- Dependencies:
--   000_extensions.sql (pgcrypto for gen_random_uuid())

-- ============================================================================
-- review_findings
-- ============================================================================

CREATE TABLE IF NOT EXISTS review_findings (
    -- Primary key
    finding_id          UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Repository and PR context
    repo                TEXT        NOT NULL,
    pr_id               INTEGER     NOT NULL CHECK (pr_id > 0),

    -- Finding classification
    rule_id             TEXT        NOT NULL,
    severity            TEXT        NOT NULL
                            CHECK (severity IN ('error', 'warning', 'info', 'hint')),

    -- Location
    file_path           TEXT        NOT NULL,
    line_start          INTEGER     NOT NULL CHECK (line_start > 0),
    line_end            INTEGER     CHECK (line_end IS NULL OR line_end >= line_start),

    -- Tool provenance
    tool_name           TEXT        NOT NULL,
    tool_version        TEXT        NOT NULL,

    -- Messages
    normalized_message  TEXT        NOT NULL,
    raw_message         TEXT        NOT NULL,

    -- Commit context
    commit_sha_observed TEXT        NOT NULL,

    -- Timestamps
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_review_findings PRIMARY KEY (finding_id)
);

-- Composite index for querying findings by repo + rule (used by pairing engine)
CREATE INDEX IF NOT EXISTS idx_review_findings_repo_rule_id
    ON review_findings(repo, rule_id);

-- Index for querying findings by location (used by disappearance verifier)
CREATE INDEX IF NOT EXISTS idx_review_findings_file_path_rule_id
    ON review_findings(file_path, rule_id);

COMMENT ON TABLE review_findings IS
    'Captured review findings from linters, CI checks, and GitHub Checks runs. '
    'Each row represents a single diagnostic finding observed at a specific commit. OMN-2535.';

COMMENT ON COLUMN review_findings.finding_id IS
    'Globally unique identifier for this finding instance.';

COMMENT ON COLUMN review_findings.repo IS
    'Repository slug in owner/name format (e.g. OmniNode-ai/omniintelligence).';

COMMENT ON COLUMN review_findings.pr_id IS
    'Pull request number within the repository.';

COMMENT ON COLUMN review_findings.rule_id IS
    'Canonical rule identifier from the originating tool '
    '(e.g. ruff:E501, mypy:return-value, eslint:no-unused-vars).';

COMMENT ON COLUMN review_findings.severity IS
    'Severity level: error, warning, info, or hint.';

COMMENT ON COLUMN review_findings.file_path IS
    'Relative path to the file containing the finding.';

COMMENT ON COLUMN review_findings.line_start IS
    'First line number of the finding (1-indexed).';

COMMENT ON COLUMN review_findings.line_end IS
    'Last line number of the finding (1-indexed, inclusive). NULL for single-line findings.';

COMMENT ON COLUMN review_findings.tool_name IS
    'Name of the tool that generated this finding (e.g. ruff, mypy, eslint).';

COMMENT ON COLUMN review_findings.tool_version IS
    'Version string of the tool at observation time.';

COMMENT ON COLUMN review_findings.normalized_message IS
    'Tool-agnostic message normalised for clustering; '
    'excludes line/column references and version-specific details.';

COMMENT ON COLUMN review_findings.raw_message IS
    'Verbatim message as emitted by the tool.';

COMMENT ON COLUMN review_findings.commit_sha_observed IS
    'Git SHA of the commit at which the finding was observed.';

COMMENT ON COLUMN review_findings.timestamp IS
    'UTC timestamp when the finding was ingested.';

-- ============================================================================
-- review_fixes
-- ============================================================================

CREATE TABLE IF NOT EXISTS review_fixes (
    -- Primary key
    fix_id              UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Foreign key to review_findings
    finding_id          UUID        NOT NULL
                            REFERENCES review_findings(finding_id)
                            ON DELETE CASCADE,

    -- Fix commit
    fix_commit_sha      TEXT        NOT NULL,

    -- Location
    file_path           TEXT        NOT NULL,

    -- Diff data stored as JSONB array of hunk strings
    diff_hunks          JSONB       NOT NULL DEFAULT '[]'::JSONB,

    -- Line range touched by the fix: [start, end] integer range
    touched_line_range  INT4RANGE   NOT NULL,

    -- Whether the fix was auto-generated by a tool
    tool_autofix        BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Timestamp
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_review_fixes PRIMARY KEY (fix_id)
);

-- Index for looking up fixes by finding
CREATE INDEX IF NOT EXISTS idx_review_fixes_finding_id
    ON review_fixes(finding_id);

-- Index for looking up fixes by commit SHA
CREATE INDEX IF NOT EXISTS idx_review_fixes_fix_commit_sha
    ON review_fixes(fix_commit_sha);

COMMENT ON TABLE review_fixes IS
    'Fix commits applied for known review findings. '
    'Each row represents a single commit believed to address a specific finding. OMN-2535.';

COMMENT ON COLUMN review_fixes.fix_id IS
    'Globally unique identifier for this fix event.';

COMMENT ON COLUMN review_fixes.finding_id IS
    'Foreign key reference to review_findings.finding_id.';

COMMENT ON COLUMN review_fixes.fix_commit_sha IS
    'Git SHA of the commit applying the fix.';

COMMENT ON COLUMN review_fixes.file_path IS
    'Relative path to the file modified by the fix.';

COMMENT ON COLUMN review_fixes.diff_hunks IS
    'JSONB array of unified-diff hunk strings for the fix. '
    'Each element is a string in standard @@ ... @@ format.';

COMMENT ON COLUMN review_fixes.touched_line_range IS
    'Inclusive integer range [start, end] of lines touched by the fix. '
    'Stored as INT4RANGE for efficient overlap queries against finding locations.';

COMMENT ON COLUMN review_fixes.tool_autofix IS
    'True if the fix was generated by an automated tool (e.g. ruff --fix).';

COMMENT ON COLUMN review_fixes.timestamp IS
    'UTC timestamp when the fix commit was observed.';

-- ============================================================================
-- finding_fix_pairs
-- ============================================================================

CREATE TABLE IF NOT EXISTS finding_fix_pairs (
    -- Primary key
    pair_id             UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Foreign key to review_findings
    finding_id          UUID        NOT NULL
                            REFERENCES review_findings(finding_id)
                            ON DELETE CASCADE,

    -- Fix commit (denormalised for query convenience without join to review_fixes)
    fix_commit_sha      TEXT        NOT NULL,

    -- Diff hunks preserved for pattern extraction
    diff_hunks          JSONB       NOT NULL DEFAULT '[]'::JSONB,

    -- Pairing confidence
    confidence_score    FLOAT       NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Resolution status
    disappearance_confirmed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Pairing method
    pairing_type        TEXT        NOT NULL
                            CHECK (pairing_type IN ('autofix', 'same_commit', 'same_pr', 'temporal', 'inferred')),

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_finding_fix_pairs PRIMARY KEY (pair_id)
);

-- Index for querying pairs by finding (used by pattern extraction)
CREATE INDEX IF NOT EXISTS idx_finding_fix_pairs_finding_id
    ON finding_fix_pairs(finding_id);

-- Index for querying high-confidence confirmed pairs (used by pattern promotion)
CREATE INDEX IF NOT EXISTS idx_finding_fix_pairs_confidence_confirmed
    ON finding_fix_pairs(confidence_score DESC, disappearance_confirmed)
    WHERE disappearance_confirmed = TRUE;

COMMENT ON TABLE finding_fix_pairs IS
    'Confidence-scored pairings of review findings and their fix commits. '
    'Produced by the Pairing Engine. Scores below 0.5 are excluded from pattern promotion. OMN-2535.';

COMMENT ON COLUMN finding_fix_pairs.pair_id IS
    'Globally unique identifier for this pairing record.';

COMMENT ON COLUMN finding_fix_pairs.finding_id IS
    'Foreign key reference to review_findings.finding_id.';

COMMENT ON COLUMN finding_fix_pairs.fix_commit_sha IS
    'Git SHA of the commit that applies the fix. Denormalised for query convenience.';

COMMENT ON COLUMN finding_fix_pairs.diff_hunks IS
    'Copy of diff hunks from the associated ReviewFixApplied event, '
    'preserved for downstream pattern extraction without additional joins.';

COMMENT ON COLUMN finding_fix_pairs.confidence_score IS
    'Confidence in [0.0, 1.0] that this fix addresses the finding.';

COMMENT ON COLUMN finding_fix_pairs.disappearance_confirmed IS
    'True if a ReviewFindingResolved event has been received for this pairing.';

COMMENT ON COLUMN finding_fix_pairs.pairing_type IS
    'How the fix was associated with the finding: '
    'autofix, same_commit, same_pr, temporal, or inferred.';

COMMENT ON COLUMN finding_fix_pairs.created_at IS
    'UTC timestamp when this pairing was created by the Pairing Engine.';

-- ============================================================================
-- pattern_candidates
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_candidates (
    -- Primary key
    candidate_id        UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Pattern classification
    rule_id             TEXT        NOT NULL,
    language            TEXT        NOT NULL DEFAULT 'python',

    -- Clustering keys
    ast_cluster_key     TEXT        NOT NULL,
    transform_signature JSONB       NOT NULL DEFAULT '{}'::JSONB,

    -- Frequency and recurrence statistics
    fix_frequency       INTEGER     NOT NULL DEFAULT 1 CHECK (fix_frequency >= 1),
    recurrence_rate     FLOAT       NOT NULL DEFAULT 0.0
                            CHECK (recurrence_rate >= 0.0 AND recurrence_rate <= 1.0),
    reintroduction_rate FLOAT       NOT NULL DEFAULT 0.0
                            CHECK (reintroduction_rate >= 0.0 AND reintroduction_rate <= 1.0),

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_pattern_candidates PRIMARY KEY (candidate_id)
);

-- Index for grouping candidates by cluster key (used by pattern reducer)
CREATE INDEX IF NOT EXISTS idx_pattern_candidates_cluster_key
    ON pattern_candidates(ast_cluster_key);

-- Index for querying candidates by rule + language (used by pattern injection)
CREATE INDEX IF NOT EXISTS idx_pattern_candidates_rule_language
    ON pattern_candidates(rule_id, language);

COMMENT ON TABLE pattern_candidates IS
    'Candidate fix patterns before promotion to the stable pattern corpus. '
    'Populated by the Pattern Candidate Reducer from high-confidence pairing data. OMN-2535.';

COMMENT ON COLUMN pattern_candidates.candidate_id IS
    'Globally unique identifier for this pattern candidate.';

COMMENT ON COLUMN pattern_candidates.rule_id IS
    'Canonical rule identifier this pattern addresses (e.g. ruff:E501).';

COMMENT ON COLUMN pattern_candidates.language IS
    'Programming language this pattern applies to (e.g. python, typescript).';

COMMENT ON COLUMN pattern_candidates.ast_cluster_key IS
    'Normalised AST-level cluster key used to group structurally similar fixes.';

COMMENT ON COLUMN pattern_candidates.transform_signature IS
    'JSONB representation of the transformation signature (AST diff fingerprint). '
    'Used for deterministic refactor tool generation.';

COMMENT ON COLUMN pattern_candidates.fix_frequency IS
    'Number of times this fix pattern has been observed.';

COMMENT ON COLUMN pattern_candidates.recurrence_rate IS
    'Fraction of sessions where this rule recurred after a previous fix attempt.';

COMMENT ON COLUMN pattern_candidates.reintroduction_rate IS
    'Fraction of sessions where this fix was applied but the finding re-appeared.';

COMMENT ON COLUMN pattern_candidates.created_at IS
    'UTC timestamp when this candidate was first created.';

COMMENT ON COLUMN pattern_candidates.updated_at IS
    'UTC timestamp when this candidate was last updated (frequency, rates).';

-- ============================================================================
-- pattern_lifecycle
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_lifecycle (
    -- Primary key
    pattern_id          UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Foreign key to pattern_candidates
    candidate_id        UUID        NOT NULL
                            REFERENCES pattern_candidates(candidate_id)
                            ON DELETE CASCADE,

    -- Lifecycle state machine
    -- States: candidate → stable → deprecated | decayed
    state               TEXT        NOT NULL DEFAULT 'candidate'
                            CHECK (state IN ('candidate', 'stable', 'deprecated', 'decayed')),

    -- State transition timestamps (NULL until the transition occurs)
    promoted_at         TIMESTAMPTZ,
    decayed_at          TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,

    -- Quality score (updated by reward signal)
    score               FLOAT       NOT NULL DEFAULT 0.0,

    -- Last update timestamp
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_pattern_lifecycle PRIMARY KEY (pattern_id)
);

-- Index for querying stable patterns by score (used by injection engine)
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_state_score
    ON pattern_lifecycle(state, score DESC)
    WHERE state = 'stable';

-- Index for looking up lifecycle record by candidate
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_candidate_id
    ON pattern_lifecycle(candidate_id);

COMMENT ON TABLE pattern_lifecycle IS
    'Lifecycle state machine records for pattern candidates. '
    'Tracks the candidate → stable → deprecated/decayed transition history. OMN-2535.';

COMMENT ON COLUMN pattern_lifecycle.pattern_id IS
    'Globally unique identifier for this lifecycle record.';

COMMENT ON COLUMN pattern_lifecycle.candidate_id IS
    'Foreign key reference to pattern_candidates.candidate_id.';

COMMENT ON COLUMN pattern_lifecycle.state IS
    'Current lifecycle state: candidate, stable, deprecated, or decayed.';

COMMENT ON COLUMN pattern_lifecycle.promoted_at IS
    'UTC timestamp when this pattern was promoted from candidate to stable. '
    'NULL until promotion occurs.';

COMMENT ON COLUMN pattern_lifecycle.decayed_at IS
    'UTC timestamp when this pattern was decayed due to high reintroduction rate. '
    'NULL unless the pattern has decayed.';

COMMENT ON COLUMN pattern_lifecycle.deprecated_at IS
    'UTC timestamp when this pattern was manually deprecated. '
    'NULL unless the pattern has been deprecated.';

COMMENT ON COLUMN pattern_lifecycle.score IS
    'Quality score updated by the reward signal integration. '
    'Higher scores indicate more reliable patterns.';

COMMENT ON COLUMN pattern_lifecycle.updated_at IS
    'UTC timestamp of the last state or score update.';
