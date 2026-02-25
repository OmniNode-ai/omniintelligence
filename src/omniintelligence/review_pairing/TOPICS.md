# Review-Fix Pairing Kafka Topics

This document defines the canonical Kafka topic names and JSON schemas for the
Review-Fix Pairing subsystem (OMN-2353). All topic names and field definitions
match the Pydantic models in `omniintelligence.review_pairing.models` exactly.

---

## Topic Names

All topics follow the ONEX canonical format:
```
onex.{kind}.{producer}.{event-name}.v{n}
```

| Enum Value | Topic String | Direction | Description |
|---|---|---|---|
| `ReviewPairingTopic.FINDING_OBSERVED` | `onex.evt.review-pairing.finding-observed.v1` | Published | A review finding was captured from any review source |
| `ReviewPairingTopic.FIX_APPLIED` | `onex.evt.review-pairing.fix-applied.v1` | Published | A fix commit was applied for a known finding |
| `ReviewPairingTopic.FINDING_RESOLVED` | `onex.evt.review-pairing.finding-resolved.v1` | Published | A finding disappearance was confirmed post-fix |
| `ReviewPairingTopic.PAIR_CREATED` | `onex.evt.review-pairing.pair-created.v1` | Published | A confidence-scored finding-fix pair was created |

---

## JSON Schemas

Each schema mirrors the corresponding Pydantic model exactly. All `datetime`
fields are ISO 8601 UTC strings (ending in `Z`). All `uuid` fields are
lowercase UUID strings (RFC 4122).

### `onex.evt.review-pairing.finding-observed.v1`

Produced by: Review Signal Adapters (linter, CI, GitHub Checks ingestion nodes)
Consumed by: Pairing Engine

```json
{
  "finding_id": "<uuid>",
  "repo": "<string: owner/name>",
  "pr_id": "<integer: > 0>",
  "rule_id": "<string: e.g. 'ruff:E501'>",
  "severity": "<string: 'error' | 'warning' | 'info' | 'hint'>",
  "file_path": "<string: relative path>",
  "line_start": "<integer: 1-indexed>",
  "line_end": "<integer | null>",
  "tool_name": "<string: e.g. 'ruff'>",
  "tool_version": "<string>",
  "normalized_message": "<string>",
  "raw_message": "<string>",
  "commit_sha_observed": "<string: 7-40 chars>",
  "observed_at": "<datetime: ISO 8601 UTC>"
}
```

### `onex.evt.review-pairing.fix-applied.v1`

Produced by: Review Signal Adapters
Consumed by: Pairing Engine

```json
{
  "fix_id": "<uuid>",
  "finding_id": "<uuid>",
  "fix_commit_sha": "<string: 7-40 chars>",
  "file_path": "<string: relative path>",
  "diff_hunks": ["<string: unified diff hunk>"],
  "touched_line_range": ["<integer: start>", "<integer: end>"],
  "tool_autofix": "<boolean>",
  "applied_at": "<datetime: ISO 8601 UTC>"
}
```

### `onex.evt.review-pairing.finding-resolved.v1`

Produced by: Finding Disappearance Verifier
Consumed by: Pairing Engine, Pattern Candidate Reducer

```json
{
  "resolution_id": "<uuid>",
  "finding_id": "<uuid>",
  "fix_commit_sha": "<string: 7-40 chars>",
  "verified_at_commit_sha": "<string: 7-40 chars>",
  "ci_run_id": "<string>",
  "resolved_at": "<datetime: ISO 8601 UTC>"
}
```

### `onex.evt.review-pairing.pair-created.v1`

Produced by: Pairing Engine
Consumed by: Pattern Candidate Reducer, metrics collectors

```json
{
  "pair_id": "<uuid>",
  "finding_id": "<uuid>",
  "fix_commit_sha": "<string: 7-40 chars>",
  "diff_hunks": ["<string: unified diff hunk>"],
  "confidence_score": "<float: 0.0 - 1.0>",
  "disappearance_confirmed": "<boolean>",
  "pairing_type": "<string: 'autofix' | 'same_commit' | 'same_pr' | 'temporal' | 'inferred'>",
  "created_at": "<datetime: ISO 8601 UTC>"
}
```

---

## Notes

- Topic names are immutable. Never hardcode topic strings; use `ReviewPairingTopic` enum values.
- All `datetime` fields must be UTC-aware when constructing Pydantic models. Naive datetimes will cause validation errors.
- `confidence_score` values below `0.5` are considered low-confidence and are excluded from pattern promotion by the Pattern Candidate Reducer.
- `diff_hunks` is a JSON array of unified-diff hunk strings. Each string begins with `@@` and includes the changed lines. The array may be empty if diff data is unavailable.

---

Reference: OMN-2535
