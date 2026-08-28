# OMN-16764 — stage-level latency breakdown of the code-context serving request

**Measured 2026-08-28 on the .201 dev lane.** Every number below was produced by a run
captured in that session; nothing is estimated or carried over from the 2026-08-14 lab note.

Environment, corpus, versions and reproduction steps:
[CONTEXT_SERVING_LATENCY_PROVENANCE.md](CONTEXT_SERVING_LATENCY_PROVENANCE.md).

> Committed rather than only attached to the ticket because OMN-16764's definition of done
> requires it: *"The stage-level breakdown from step 1 is committed, not just posted — future
> work needs to diff against it."* Re-measure against this file; do not replace it silently.

---

## 1. Headline

| Measurement | Value |
| --- | --- |
| One-shot CLI request, wall clock, 30 consecutive runs | p50 **3.50 s**, p95 **3.65 s**, min 3.37 s, max 3.74 s |
| Same request, warm process (imports already paid), 25 runs | p50 **0.857 s**, p95 **1.013 s** |
| Historical number this ticket exists to move | 2.687 s |

The 2026-08-14 figure of 2.687 s reproduces in shape. The path measured here is the same
one-shot `python -m omniintelligence.code_projection.context_serving` invocation against a
live Qdrant, a live embedding endpoint, and a real on-disk artifact store.

**The single most important result: 69 % of the 3.50 s is spent before the request starts.**
Module import and interpreter startup cost 2.41 s. The actual retrieval work is 0.86 s.

---

## 2. Phase split (py-spy wall-clock profile, 500 Hz, 4.322 s of samples)

| Phase | Time | Share |
| --- | --- | --- |
| Interpreter start + module import | **2.406 s** | 55.7 % |
| Request execution (`cli._run` → `CodeContextProcessor.process`) | **1.116 s** | 25.8 % |
| Remainder (CLI module body, teardown, profiler overhead) | 0.800 s | 18.5 % |

Inside the import phase, one subtree dominates:

| Import subtree | Time | Share of total |
| --- | --- | --- |
| `omniintelligence/__init__.py:29` → `nodes.node_quality_scoring_compute` → `omnibase_core.nodes` → `omnibase_core.models.*` | **1.80 s** | 41.6 % |
| `qdrant_client` | 0.43 s | 10.0 % |

The 1.80 s subtree is Pydantic model-class construction (`_dict_not_none`,
`complete_model_class`, `_decorator_infos_for_class`) for the whole `omnibase_core` model
tree. **None of it is used by context serving.** It is pulled in eagerly by the
`omniintelligence` package `__init__`.

---

## 3. Per-stage table (warm process, 25 runs, p50 = 0.857 s)

| # | Stage | Calls / request | Mean | Total / request | % of request |
| --- | --- | --- | --- | --- | --- |
| 2a | Embedding HTTP — query (1 text) | 1 | 78.6 ms | 78.6 ms | 9.2 % |
| 2b | Embedding HTTP — **re-embed 20 candidates** | 1 | 78.6 ms | 78.6 ms | 9.2 % |
| 3 | Qdrant vector search (`query_points`) | 1 | 6.3 ms | 6.3 ms | 0.7 % |
| 4 | Artifact resolve, per candidate | 20 | 25.8 ms | **516.2 ms** | 60.2 % |
| 4a | └ `load_current` (incl. 4 more inside search) | 24 | 25.7 ms | **615.8 ms** | 71.9 % |
| 4b | └ └ `read_content_artifact` (nested in 4a) | **2704** | 0.07 ms | 188.3 ms | 22.0 % |
| 5 | tiktoken token counting | 41 | 1.46 ms | 59.9 ms | 7.0 % |

Rows 4, 4a and 4b nest — do not add them. 4a exceeds 4 because four `load_current` calls
happen inside `search` (the current-generation filter), not inside `resolve`.

Request outcome for every run in the table: 20 candidates considered, 8 items returned,
15 970 context tokens, 143 886-byte response.

### Rough non-overlapping attribution of the 0.857 s

| Bucket | Time | Share |
| --- | --- | --- |
| Artifact-store re-validation (`load_current` ×24) | 616 ms | 71.9 % |
| Embedding round trips (×2) | 157 ms | 18.3 % |
| tiktoken counting (×41) | 60 ms | 7.0 % |
| Qdrant search | 6 ms | 0.7 % |
| Everything else (pack assembly, digests, pydantic) | ~18 ms | 2.1 % |

---

## 4. The ticket's candidate list, scored against measurement

The ticket listed five suspects "in the order they are most likely to dominate". Measured,
that order is close to inverted.

| Ticket's suspect | Measured | Verdict |
| --- | --- | --- |
| The embedding call | 157 ms of 857 ms warm; 4.5 % of the 3.50 s CLI wall | Real but second-order — **and half of it is avoidable** (see H3) |
| Vector search and its `ef_search`/`k` knobs | **6.3 ms**, 0.7 % | Not the problem. Tuning HNSW here would win nothing |
| Policy / provenance checks serialized per candidate | Yes — this *is* the dominant cost, but as artifact-store I/O, not CPU policy logic | **Confirmed, and it is #1** |
| Per-candidate store reads — is this N+1? | **Worse than N+1: it is N×M** | **Confirmed, and it is the root cause** |
| Pack assembly and digest computation | 60 ms tiktoken + ~18 ms assembly | Real, superlinear, but small in absolute terms |

Not on the ticket's list and larger than every item on it: **process startup and module
import, 2.41 s.**

---

## 5. Top hotspots by self-time

### H1 — Module import of the `omniintelligence` package: 2.41 s (69 % of the 3.50 s CLI wall)

`omniintelligence/__init__.py:29` eagerly imports `nodes.node_quality_scoring_compute`,
which transitively builds the entire `omnibase_core` Pydantic model tree — 1.80 s of
model-class construction that context serving never touches. `qdrant_client` adds 0.43 s.

This cost is paid **per request** as long as serving is a one-shot process. It is paid
**once per process lifetime** behind a resident server. This is the largest single lever in
the whole profile and it is not a retrieval-quality trade at all.

### H2 — `CodeProjectionArtifactStore.load_current`: 616 ms (72 % of the warm request)

Called 24 times for one request; 2704 content-artifact reads result.

The mechanism is `artifacts.py:_validate_contracted_artifacts`, invoked at the end of every
`load_current`. It re-reads and SHA-256-verifies **every semantic document in the entire
batch** — not just the one document the candidate needs:

```python
for document in batch.semantic_documents:
    content = self._resolve_artifact_ref(document.content_ref, ...)
    if sha256_hex(content) != document.sanitized_content_hash_sha256:
```

So serving one 8-item context pack performs a **full integrity re-validation of ~15 source
files' complete projections**: 24 batch-JSON parses (median 59 KB, max 179 KB) plus 2704
content-artifact reads and hashes. There is no per-request memoization — candidates from the
same `source_id` each pay the whole cost again (20 resolves over ~15 unique sources).

### H3 — Two embedding round trips, one of them redundant: 157 ms (18 %)

Stack traces confirm two distinct call sites:

```
_embed:933 <- search:1554 <- process:245     n_texts=1     # the query — necessary
_embed:933 <- search:1681 <- process:245     n_texts=20    # re-embeds every candidate
```

The second call re-embeds all 20 retrieved candidates to check them against
`reembedding_cosine_threshold_basis_points = 9990` — a vector-drift verification performed
on the **read** path, duplicating work the write path already did. It costs ~79 ms per
request and scales with `candidate_limit`.

Worth noting for whoever tunes this: the *endpoint* is fast. A raw `curl` to
`.201:8002/v1/embeddings` returns in **4–5 ms** warm. The client-side path costs 78.6 ms.
That ~15× gap is unexplained by the endpoint and is its own worthwhile investigation.

---

## 6. Two additional findings

### F1 — tiktoken's BPE load is a 941 ms cold cost, cached in `/tmp`

| Condition | Time |
| --- | --- |
| `tiktoken.get_encoding("cl100k_base")`, cold | **941 ms** |
| Same, warm | 67 ms |

The cache lands in `/tmp/data-gym-cache` (no `TIKTOKEN_CACHE_DIR` set). On a fresh container
or after a reboot the first request pays a ~1 s network download. `get_tokenizer()` is
`lru_cache`'d, so this is once per process — but in a one-shot CLI, "once per process" means
"once per request". Any containerised deployment should pre-warm this file into the image.

### F2 — Pack assembly is superlinear in item count

`_render_generation_context` runs **inside** the per-candidate selection loop
(`service.py:281`), re-serialising every already-selected item and re-tokenising the entire
accumulated context on each iteration.

Measured by sweeping `max_items`:

| max_items | items returned | resolve calls | wall | search | resolve | assembly |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 0.323 s | 0.296 s | 0.023 s | 0.0038 s |
| 2 | 2 | 2 | 0.346 s | 0.294 s | 0.045 s | 0.0061 s |
| 3 | 3 | 3 | 0.366 s | 0.289 s | 0.068 s | 0.0091 s |
| 5 | 5 | 5 | 0.570 s | 0.445 s | 0.110 s | 0.0140 s |
| 8 | 8 | 9 | 0.691 s | 0.317 s | 0.348 s | 0.0259 s |
| 10 | 8 | 20 | 0.779 s | 0.298 s | 0.416 s | 0.0652 s |

Assembly grows **17×** from 1 to 10 items where linear would be 10× — confirming the
quadratic shape. In absolute terms it stays small (65 ms) because the 16 000-token budget
caps the accumulated text. It is a real defect but not where the seconds are.

The same sweep exposes a second effect: at `max_items=10`, **20** resolve calls produce only
**8** items. Rejected candidates (budget overrun, duplicate) still pay a full ~26 ms
`load_current`. Rejection is as expensive as acceptance.

---

## 7. A contract gap found while building the reproduction

The operator ingest CLI writes

```python
scope_ref=f"tenant:{tenant_id}:repository:{repository_id}"        # __main__.py:141
```

but `ModelCodeContextAuthorizationProfile` requires the derived form produced by
`derive_repository_policy_scope_ref`, which appends `:instance:<instance_id>`. A projection
produced by the shipped ingest CLI therefore **cannot** be served by the shipped
context-serving path — the grant validator rejects the profile with *"repository policy
scope does not match its tenant and instance"*, and if the request is adjusted to satisfy
the grant, the resolver then rejects every candidate on `policy.scope_ref` mismatch.

The corpus for this profile was produced with a one-line local change to the ingest CLI
(appending `:instance:canonical`) so the two surfaces agree. **That change exists only in a
throwaway checkout on the dev-lane host. It is not committed and no PR was opened.** It is
reported here because it looks like a genuine defect in one of the two surfaces, and it will
block anyone else trying to reproduce this measurement.

---

## 8. What would actually close the gap

Ranked by measured saving. No number here is a guess — each is the measured cost of the work
being removed.

| # | Change | Measured saving | Quality risk | Status |
| --- | --- | --- | --- | --- |
| 1 | Serve from a resident process instead of a one-shot CLI | **2.41 s** (69 % of wall) | **None** — no retrieval behaviour changes | Open — architecture decision, see §8.1 |
| 2 | Resolve only the candidate's own document instead of re-validating the whole batch | up to **~600 ms** of the 616 ms | Weakens a per-request integrity check to per-document. Needs a deliberate decision, not a silent one | Open — integrity trade, not taken |
| 3 | Memoize `load_current` per `source_id` per request | ~170 ms (24 calls → ~15) | None — same bytes, same digests | Done — PR #862 |
| 4 | Drop or sample the candidate re-embedding drift check on the read path | **~79 ms** | Removes a live drift check. Move it to the write path or a background sweep | Open — quality trade, not taken |
| 5 | Hoist `_render_generation_context` out of the selection loop; track byte/token totals incrementally | ~50 ms at 10 items, more as budgets grow | None if the accounting is exact | Partly done — PR #863 (serialisation half only; the tokenisation half is deliberately untouched, see that PR) |
| 6 | Resolve candidates concurrently instead of serially | up to ~480 ms of the 516 ms | None; bounded concurrency needed | Done — PR #864 |
| 7 | Pre-warm the tiktoken BPE cache into the image / set `TIKTOKEN_CACHE_DIR` | 941 ms on cold start only | None | Held — changes the deployed image, awaiting lane-owner sign-off |

Items 1 + 3 + 4 + 7 are all quality-neutral and together account for the large majority of
the gap. **The sub-500 ms budget looks reachable without trading retrieval quality at all**,
which is the opposite of the trade the ticket was braced for.

Item 2 is the only one that touches an integrity guarantee, and on these numbers it may not
be needed — which is worth knowing before anyone spends the guarantee.

### 8.1 — The open question the budget depends on

Item 1 is the largest lever by a wide margin, and whether it is even available depends on a
question this profile cannot answer: **does the sub-500 ms budget measure a resident process
or the one-shot CLI?**

On these numbers ~2.41 s of import is irreducible for a one-shot invocation. Trimming it
(PR #861 defers the `omnibase_core` subtree out of the package root) helps, but the shape
does not change: a fresh interpreter must still import `qdrant_client`, `tiktoken`, and the
serving modules themselves.

So:

* If the budget measures a **resident process**, sub-500 ms is plausible — the warm p50 is
  already 0.857 s and items 3–7 attack most of it.
* If it measures the **one-shot CLI**, sub-500 ms is not reachable by optimization at all,
  and OMN-16764's definition of done resolves on its *re-litigation* branch — a recorded
  measured number plus a note on what would have to change architecturally.

This is a scoping decision for the lane owner, not something to be settled by picking
whichever reading makes the number look better.

---

## 9. Caveats — read these before treating any number as a production forecast

1. **The corpus is small.** 811 points in the profiled tenant across ~15 files. Qdrant
   reports `indexed_vectors_count: 0` with `indexing_threshold: 10000`, so **no HNSW index
   is built** and search is a brute-force scan. The 6.3 ms search figure will not hold at
   production scale. It is currently 0.7 % of the request; it has a lot of room to grow
   before it matters, but this profile says nothing about how HNSW behaves here.
2. **This is not the same physical corpus as the 2026-08-14 run.** That run's artifact tree
   no longer exists on either the dev-lane host or the operator workstation. The corpus here
   was rebuilt on the dev lane from the same repository with the same embedding model and
   model version.
3. **The one-shot-CLI import cost is a property of the current entrypoint**, not of the
   retrieval algorithm. If the production serving surface is a resident process, H1 mostly
   disappears and H2 becomes the dominant cost.
4. **py-spy adds overhead.** The profiled run sampled 4.322 s against an unprofiled p50 of
   3.50 s. Use the unprofiled wall-clock numbers for absolute claims and the profile for
   proportions.
5. **`load_current` timings include OS page-cache effects.** Repeated runs on a warm cache
   are the best case; a cold cache would be worse, not better.
6. **No number here has been re-measured since the optimizations in §8 landed.** This file
   records the *pre-optimization* state, which is what makes it useful to diff against. A
   post-optimization run belongs beside it, not on top of it.
