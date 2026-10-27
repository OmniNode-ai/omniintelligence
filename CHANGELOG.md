# Changelog

All notable changes to `omninode-intelligence` are recorded here. Versions follow
[Semantic Versioning](https://semver.org/).

## [0.25.0] - 2026-10-27

A minor release that catches up the changes made since 0.24.0, cut deliberately as a minor
rather than a patch because of how much accumulated. It covers 112 commits to `src` and
`pyproject.toml` between `v0.24.0` and this release.

### Added

- Hostile review: voters are read from a contract overlay (`review_voters_overlay.v2`, with
  personas), each voter can name ordered overflow endpoints, and voters can run through the
  Anthropic API or a Claude Code account pool.
- Hostile review: findings block only when several distinct models agree. Two voters get distinct
  sampling and focus, and the result names any reviewer it could not reach.
- Hostile review: a signed off-CI review receipt can stand in for a voter that timed out or was
  unavailable.
- Hostile review: a judge node and a `judge-rejections` command assess rejected findings. A gated
  review runs with the reviewed repository's standing rules or not at all, and every voter is told
  the repository's name.
- Review rubric files, with a loader that keeps to a token budget and a check node.
- `cli_review` records each voter's result, and the receipt reviewer records its findings.
- A compact verdict prompt (v2) with a typed call response.
- Code intelligence: bounded code-context packs served after an authorization check, a frozen
  deterministic code-projection seam, and a retrieval-quality benchmark harness for context packs.
- `CiErrorClassifier` and `DebugRetrieval` compute nodes.
- Dispatch-worker-completed bridge handlers in the dispatch engine.
- A Cursor hook event effect node, registered under `onex.nodes`.
- A dependency-provenance gate with a staleness threshold for cross-repository git pins.

### Changed

- Dispatch moved off the removed core `MessageDispatchEngine`.
- `tools/` and `clients/` were restructured to the ONEX taxonomy, and boundary `@dataclass`
  types became Pydantic models.
- Every node contract declares a top-level `version: "X.Y.Z"` string.
- The reviewer model id is resolved at runtime instead of being declared. Retired model names and
  lab endpoint defaults were removed from the package.
- Torch and transformers moved to the opt-in `rl` dependency group, so the review path installs
  without them. `numpy` and `scipy` are declared directly.
- Dependencies are resolved from PyPI, not git sources: `omnibase-core` is `>=0.47.0,<0.48.0`, and
  `omnimarket` comes from PyPI so the release cascade can move `omnibase-infra`.
- Stray topic literals moved into the canonical registries, and scattered `os.environ` endpoint
  reads were removed.
- Context-pack scoring is faster: the quality-scoring import is deferred, `load_current` is
  memoised within a request, and each item's payload is built once.

### Fixed

- Hostile review: an unparseable reply counts as a failed vote rather than a clean one, and its
  retry gets a larger token budget. A Claude reply cut at `max_tokens` takes the JSON-only retry.
  A finding that says there is no defect is dropped and recorded.
- Hostile review: the diff is bounded by the model's context limit, oversized diffs fall back to
  per-file review, the review deadline scales with the chunk count, chunk budgets are reserved for
  overflow, and an exhausted budget fails the voter as a timeout.
- Hostile review: the quorum counts distinct endpoint and model pairs, and a full-SHA workflow pin
  is treated as compliant.
- `cli_review` emits a valid passed verdict for an empty diff.
- The routing-feedback upsert names only columns the table has, and the legacy bare-topic drain was
  removed.
- Pattern storage: the dispatch bridge event and its validation were fixed.
- The `RewardSignal` contract schema was restored, verdicts are lowercase, and
  `ModelCostProvenance` is constructed correctly.
- Timestamps use UTC instead of local wall-clock time.
- Hardcoded paths were removed, the code-quality source read resolves the worktrees root correctly,
  and the ingest CLI derives its policy scope so its projections can be served.
- Four nodes gained the `contract.yaml` they were missing.

### Removed

- The unused `PyPDF2` dependency.
- High-confidence dead code.
