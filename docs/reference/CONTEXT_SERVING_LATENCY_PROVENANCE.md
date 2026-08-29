# OMN-16764 profile bundle — environment provenance

Everything needed to re-run the measurements in
[CONTEXT_SERVING_LATENCY_TIMINGS.md](CONTEXT_SERVING_LATENCY_TIMINGS.md) and get comparable
numbers.

> The flamegraphs (`omn16764-wallclock.svg`, `omn16764-wallclock.speedscope.json`,
> `omn16764-oncpu.svg`) and the harness bundle (`omn16764-harness.tar.gz`: `request.json`,
> `auth.json`, `run.sh`, `final.py`, `sweep.py`, `analyze2.py`) are attached to OMN-16764
> rather than committed here — they are binary/large capture artifacts, not text that future
> work diffs against. The two Markdown files are committed because the ticket's definition
> of done requires the breakdown to be committed, not only posted.

## Capture

| Field | Value |
| --- | --- |
| Captured | 2026-08-28 |
| Host | `192.168.86.201`, Linux 7.0.0-30-generic x86_64, 32 vCPU, 91 GiB RAM |
| Lane | **dev only** — compose project `omnibase-infra`. stability-test / judge / prod untouched |
| Working dir on host | `/home/jonah/omn16764-profile` (throwaway; not a managed clone) |

## Coordination gate

Latest dev-lane refresh receipt before profiling began:

| Field | Value |
| --- | --- |
| Receipt | `/home/jonah/.omnibase/state/dev_lane_refresh/history/20260828T005554Z-4529c3486a8b.json` |
| `ts_utc` | `2026-08-28T01:04:46Z` |
| `result` | `SUCCESS` |
| `health_gate.health_ok` | `true` (`status=healthy`) |
| `health_gate.cluster_healthy` | `true` |
| `health_gate.manifest_count` | 301 (floor 288) |
| `health_gate.revision_readback_ok` | `true` |
| `rollback.triggered` | `false` |

No refresh was in progress (`latest.json` mtime matched the newest history receipt; no build
running). Profiling proceeded against the stable post-refresh lane.

## Code under profile

| Field | Value |
| --- | --- |
| Repo | `OmniNode-ai/omniintelligence` |
| Branch | `dev` |
| Commit | `5d83700586cad7c4ca49b4a4996dad7936a59076` |
| Subject | `chore(deps): bump omnibase_infra to 0.38.11 (#860)` |
| Date | 2026-08-28 04:39:42 -0400 |

**Local modification (profiling harness only, never committed, no PR):** one line in
`src/omniintelligence/code_projection/__main__.py:141`, appending `:instance:canonical` to
the ingest policy `scope_ref` so the ingest CLI and the context-serving authorization model
agree. See TIMINGS.md §7. The context-serving code path itself is **completely unmodified** —
no file under `context_serving/`, `artifacts.py`, or `qdrant.py` was touched.

> **Resolved by OMN-16898 (2026-08-28).** The defect that forced the local patch is fixed on
> `dev`: the ingest CLI now derives the policy scope through the shared
> `derive_repository_policy_scope_ref` and accepts `--repository-instance-id`
> (default `canonical`), so a projection it emits is admitted by the shipped serving grant
> without modification. Reproducing this measurement no longer requires a throwaway checkout.
> Note that the CLI now also requires `--tenant-id` to be a canonical UUID, since the serving
> contract types every tenant as one; the slug tenants it previously accepted could never be
> served. The numbers in this document predate that fix and are retained as recorded.

## Runtime dependencies

| Component | Endpoint | Version / identity |
| --- | --- | --- |
| Qdrant | `http://127.0.0.1:6333` | v1.16.3, commit `bd49f45a8a2d4e4774cac50fa29507c4e8375af2`, container `omnimemory-qdrant` |
| Collection | `code_semantic_v2` | vector `code_semantic_v2`, size 1024, distance Dot, HNSW m=16 ef_construct=100, `indexing_threshold=10000` |
| Embedding | `http://127.0.0.1:8002` | vLLM serving `text-embedding-qwen3` (Qwen3-Embedding-0.6B), 1024-dim, max_model_len 8192 |
| Embedding model version | | `qwen3-embedding-0.6b-lab-2026-08-14` |
| Postgres (ingest only) | `127.0.0.1:5436/omniintelligence` | container `omnibase-infra-postgres`, `postgres:16-alpine` |
| Memgraph (ingest only) | `bolt://127.0.0.1:7687` | container `omnimemory-memgraph`, `memgraph/memgraph:2.18.1` |
| Dev lane runtime image | | `sha256:e08c5d5630848886619683582a8d9645c60b715ef1f239de1eb589334be0938c`, revision label `4529c3486a8b` |

The dev-lane runtime container itself is **not** on the profiled path — context serving is a
standalone CLI process. The runtime image digest is recorded only to pin which lane state
the shared Qdrant/embedding/Postgres services belonged to.

## Tooling

| Tool | Version |
| --- | --- |
| Python | 3.12.3 (system `/usr/bin/python3`, throwaway venv at `/home/jonah/omn16764-profile/venv`) |
| py-spy | 0.4.2 |
| omniintelligence | installed `-e` from the commit above |

`.201` has no `uv`; the venv was built with `python3 -m venv` + `pip`, per host convention.

### Why py-spy launch mode, not attach

The measured serving surface is a **one-shot CLI process**
(`python -m omniintelligence.code_projection.context_serving`), not a long-lived server.
There is no resident process to attach to and no container to grant `SYS_PTRACE`. py-spy was
therefore used in launch mode — `py-spy record ... -- ./run.sh` — which profiles the whole
process from its first instruction. This is strictly better than attach for this workload:
it captures the import phase, which turned out to be 69 % of the wall time and would have
been entirely invisible to an attach-after-startup profile.

`--idle` was passed for the wall-clock captures so time blocked on network and disk is
attributed rather than dropped.

## Corpus

| Field | Value |
| --- | --- |
| Tenant | `77777777-7777-4777-8777-777777777777` (isolated profiling tenant) |
| Repository | `lab/omn-16764/omniintelligence` |
| Policy scope | `tenant:77777777-7777-4777-8777-777777777777:repository:lab/omn-16764/omniintelligence:instance:canonical` |
| Source files ingested | 15 (from `src/omniintelligence/code_projection/`) |
| Qdrant points in tenant | 811 |
| Artifact tree | 496 files, 3 088 398 bytes, at `/home/jonah/omn16764-profile/artifacts` |
| Batch objects | 30 JSON files, median 59 391 B, max 179 382 B, total 2 360 635 B |

The 2026-08-14 lab corpus (`lab/omn-16061/omniintelligence`, tenant `omninode-dev`) is still
present in the same Qdrant collection — 510 points — but is **not usable** for a context
request: its `tenant_id` is the literal string `omninode-dev`, and
`ModelCodeContextRequest.tenant_id` requires a canonical UUID. Its artifact tree no longer
exists on any reachable host. That is why a fresh corpus was built.

## Request under profile

`request.json`, 790 bytes (the 2026-08-14 canonical request was 777 bytes), sha256
`1054f536767aed1d98aee92268293bf436d4f2369daa65ef136fe4341801ae9c`.

```json
{"candidate_limit":20,"correlation_id":"22222222-2222-4222-8222-222222222222",
 "kind":"code_context_request","max_context_bytes":131072,"max_context_tokens":16000,
 "max_items":10,"min_score_basis_points":0,"policy_scope_ref":"tenant:...:instance:canonical",
 "principal_id":"omn-16764-profiler",
 "query_text":"how does the artifact store promote a current code projection batch",
 "repository_id":"lab/omn-16764/omniintelligence","repository_instance_id":"canonical",
 "request_id":"11111111-1111-4111-8111-111111111111","schema_version":"1.0.0",
 "tenant_id":"77777777-7777-4777-8777-777777777777","timeout_ms":30000}
```

`auth.json`, 900 bytes, sha256
`2c71616e4a56b3876c92f73423b1bdbcb1959e3f999f23624db6af1c3d31e55c` — bound at runtime via
`CODE_CONTEXT_AUTHORIZATION_FILE` + `CODE_CONTEXT_AUTHORIZATION_SHA256`.

Both files are in the harness bundle attached to the ticket. Neither contains a credential;
the authorization profile is a scope grant only.

Response for every timed run: 20 candidates considered, 8 items returned, 15 970 context
tokens, 143 886-byte response.

## Files in the attached bundle

| File | What it is |
| --- | --- |
| `omn16764-wallclock.svg` | py-spy flamegraph, wall clock (`--idle`), 500 Hz, 2332 samples |
| `omn16764-wallclock.speedscope.json` | Same capture in speedscope format — open at speedscope.app |
| `omn16764-oncpu.svg` | py-spy flamegraph, on-CPU only, 500 Hz, 2110 samples — contrast with wall clock to separate compute from I/O wait |
| `request.json`, `auth.json` | The exact request and authorization profile |
| `run.sh` | The one-shot invocation, as profiled |
| `final.py` | Instrumented stage-timing harness (wraps the boundaries; does not modify serving code) |
| `sweep.py` | `max_items` sweep that exposes the superlinear assembly cost |
| `analyze2.py` | Speedscope phase/subsystem attribution used for TIMINGS.md §2 |

## Reproducing

```bash
# on the dev-lane host
cd /home/jonah/omn16764-profile
source env.sh                      # Qdrant / embedding / Postgres / Memgraph bindings
./run.sh                           # one request, wall clock
./venv/bin/python final.py 25      # warm-process stage table
./venv/bin/python sweep.py         # max_items sweep
py-spy record --idle --rate 500 --format speedscope -o out.json -- ./run.sh
```

`env.sh` holds the Postgres password for the dev-lane database and is `chmod 600` on the
host; it is deliberately **not** included in the bundle. Every other binding it sets is
listed in the runtime-dependencies table above.

Note that the paths above are on the operator-owned dev-lane host and are not reachable from
a contributor workstation. Reproducing this measurement requires dev-lane access; ask the
lane owner (see OMN-16764 §8) rather than assuming an equivalent local setup will produce
comparable numbers.

## Lane discipline

Read-only against stability-test, judge, and prod — those lanes were listed once to confirm
port separation and never touched again. All writes (corpus ingest into an isolated tenant,
throwaway venv, profile output) landed on the dev lane and under `/home/jonah`, both
pre-authorized mutable surfaces. No deploy, restart, retag, or compose mutation of any lane.
No PR, no ticket-state change.
