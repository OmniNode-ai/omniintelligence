## v0.25.1 (2026-11-01)

### Release
- Cut omninode-intelligence from dev at 0.25.1 by the scheduled release train.
- 21 release-relevant commit(s) merged since v0.25.0.
- Opened by the release train, which cuts only when the repo's declared lab-evidence premise holds for the exact candidate commit.

### Included Since v0.25.0
- refactor: hand-built nodes resolve from container binding modules, handler_hand_construction 67 to 63 (#1186)
- refactor: read literal_topic slice rf1550-c6 topics from node contracts (#1184)
- refactor: literal_url test endpoints move into contract files, slice rf1410-c3 (#1182)
- refactor: model names and paths come from the overlay and fixtures, literal_path 12 to 0, literal_model_name 9 to 0 (#1185)
- refactor: remaining literal timeouts read from runtime_timeouts.yaml, literal_timeout 16 to 0 (#1181)
- refactor: literal_timeout slice rf1320-c2 reads timeouts from contracts (#1180)
- feat: contracts_and_di slice rf1120-c3 - runtime bind address and ports into a contract, in-memory stand-ins out of runtime code and test conftests (#1179)
- refactor: model names come from the deployment overlay, literal_model_name 30 to 9 (#1178)
- feat: move runtime, code projection and node default timeouts into runtime_timeouts.yaml (#1175)
- refactor: plan reviewer strategies take one typed request model (#1167)
- refactor: topic registry reads its topics from node contracts (#1177)
- refactor: literal URLs in code projection, plan reviewers, review bot and log sanitizer move to contracts (#1174)
- refactor: quality scoring and intent classifier handlers become handler classes (T2.4a slice 2) (#1172)
- refactor: rebase four-node handler-class slice onto dev (#1169)
- feat: read runtime and dispatch topics from node contracts (#1173)
- Rebase dispatch head 7faf127763c2cf19fc15beafec5f7791e982ef8d onto origin/dev e2597fd3feaa05efa106dafa1c848fc4ad73f1cd (#1171)
- feat: node_pattern_extraction_compute eleven handler classes bound by the contract (#1170)
- refactor: pattern learning and pattern assembler handlers become handler classes (#1168)
- feat: move adapter timeouts into adapter_settings.yaml (#1164)
- refactor: six single-request compute handlers become handler classes (T2.4a slice 1) (#1162)
- feat: move review_pairing timeouts and codex dirs into a contract file (#1163)

## v0.25.0 (2026-10-27)

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
