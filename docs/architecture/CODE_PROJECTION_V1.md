# Deterministic code projection v1

**Status:** runnable, namespaced dev-lab application canary (OMN-16061)
**Production runtime authority:** none; the deployed event ingress remains held
**Workspace authority:** `$OMNI_HOME/docs/standards/OMNINODE_DETERMINISTIC_TRUTH_DOCTRINE.md`

## Decision

`omniintelligence.code_projection` owns the source-scoped serialization contract
and a one-shot application command for the dev lab. The command reads a real
Python, TypeScript, or JavaScript file; applies the existing deterministic
extractors, classifier, quality scorer, and semantic analyzer; stages immutable
content-addressed evidence; materializes the result into the existing
OmniIntelligence Postgres tables and Memgraph; and reads the projection back
before advancing current state.

This is a real application feature, but it is deliberately namespaced to
logical repository IDs beginning with `lab/`. It does not register a node,
consumer, topic, API, or service entry point; publish source through Kafka;
invoke a model; provision storage; or claim production ingress authority. The
operator command runs inside the existing effects runtime so it uses the lab's
injected Postgres and Memgraph clients.

The package remains internal to this lane. A later OmniMemory implementation
must consume the checked-in canonical JSON and schema digest through its own
DTOs; neither product package may import the other. Public export, production
runtime activation, or an importer outside this lane triggers the
ownership-relocation gate in the workspace plan.

The two existing code-file-discovered runtime events remain unchanged. They are
both still imported by different live paths, so event reconciliation belongs to
a separate runtime ticket.

## Contract shape

`ModelCodeProjectionBatch` is one full source snapshot or explicit tombstone.
Its header pins schema, projection, reducer, and identity versions. The batch
also contains:

- a logical repository ID and normalized POSIX repository-relative path;
- a source-partition cursor with an explicit authority and monotonic sequence;
- content-addressed source and transform-manifest references;
- a closed privacy, access, trust, redaction, and retention envelope;
- source-owned nodes, closed relationship edges, and semantic-document refs;
- an exact replay manifest and record checksum.

An empty successfully processed source is a snapshot with no records. It is not
a deletion. Source deletion and policy revocation are distinct tombstone
operations. Parse or extraction failure does not produce an authoritative empty
snapshot.

## Identity rules

Every ID is a domain-separated SHA-256 over canonical JSON. The v1 domains,
prefixes, and payloads are:

| Record | Prefix | Canonical identity payload |
| --- | --- | --- |
| Source | `csrc_v1_` | identity version, logical repository ID, normalized relative path |
| Node | `cnode_v1_` | identity version, source ID, entity kind, qualified name |
| Edge | `cedge_v1_` | identity version, source ID, source node ID, relationship kind, target node ID |
| Semantic document | `cdoc_v1_` | identity version, source ID/hash, chunk key/kind/span, anchor, chunker version, sanitized-content hash |
| Batch | `cbatch_v1_` | the complete versioned batch payload excluding the two self-referential batch-ID fields |

UUIDs, wall-clock time, checkout roots, absolute paths, transport correlation
IDs, and source revision labels never participate in identity or ordering. Any
formula change requires an identity-version and prefix/domain bump.

## Canonical bytes

Wire output is UTF-8 JSON with NFC-normalized strings, lexicographically sorted
object keys, compact separators, no floating-point values, canonically sorted
and unique record arrays, and exactly one terminal LF framing byte. Confidence
is represented as integer basis points.

The parser rejects duplicate keys (including keys that collide after NFC),
invalid UTF-8, noncanonical bytes, unknown fields, coercible-but-wrong scalar
types, unsorted or duplicate records, unstable IDs, checksum drift, manifest
drift, and inline source/docstring/chunk text.

## Endpoint, privacy, and retention rules

Every accepted edge endpoint and semantic-document anchor resolves to a node in
the same source-owned batch. A producer must materialize an unresolved symbol
as a deterministic `external_symbol` node or emit a separate typed extraction
diagnostic. Silent relationship drops and foreign-source ownership are invalid.

Raw source and sanitized semantic content live behind distinct
content-addressed artifact references. A batch contains their hashes and refs,
not their bytes. The lab command retains the exact authorized source bytes and
the exact extractor contract in its operator-supplied artifact root, so its
policy says `redaction_state=not_required`; it never falsely labels those bytes
as sanitized. Arbitrary docstrings, source text, vector bytes, model IDs, local
paths, and generic metadata dictionaries are not batch wire fields.

Staged source objects are immutable evidence. They can remain after a failed
application and remain available after a tombstone; tombstoning removes the
derived Postgres/Memgraph projection, not source history. Artifact-root access,
retention, and eventual purge are operator responsibilities in this canary.

## Ordering, application, and recovery

Only `cursor.sequence`, compared within the same source partition and cursor
authority, orders facts. Source revision and Git SHA are provenance.

The planner is pure and the dev-lab command applies its decision as follows:

| Condition | Outcome |
| --- | --- |
| No current manifest or higher incoming sequence | `replace` with exact sorted delete/upsert sets |
| Same sequence and same batch ID | `noop` after live readback, or `repair` if drift is detected |
| Same sequence and different batch ID | `conflict` |
| Lower incoming sequence | `stale` |

Different source partitions or cursor authorities are not comparable. A→B→A
at increasing sequences restores A deterministically even when the third source
hash matches the first.

One durable artifact root is the cursor authority for this canary. A per-source
interprocess file lock covers current-state read, extraction, application,
readback, and pointer promotion. Operators must use that same root and a single
writer namespace. Copying or discarding it creates a different authority and is
not supported.

Postgres applies each source in a transaction. Memgraph is a derived index and
cannot participate in that transaction, so an interrupted cross-store apply can
be briefly partial. The current pointer advances only after both stores pass
readback. Retrying from the same artifact root deterministically reapplies or
repairs the projection.

## Operator surface

```text
uv run python -m omniintelligence.code_projection ingest \
  --root <mounted-repository-root> \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <durable-artifact-root>

uv run python -m omniintelligence.code_projection inspect \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <same-durable-artifact-root> \
  --symbol <exact-qualified-name>

uv run python -m omniintelligence.code_projection tombstone \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <same-durable-artifact-root>
```

`ingest` emits a JSON receipt containing the replay decision, source and batch
IDs, artifact digests, write counts, and verified readback counts and ID-set
digests. `inspect` proves an exact symbol, its deterministic labels, and its
relationships from the live read model. `tombstone` proves zero source-owned
records in both stores while preserving immutable evidence.

Readback verifies every source-owned ID and endpoint, complete canonical
node/edge payload digests, label payloads, relationship
trust/confidence/context properties, batch identity, and policy/provenance
digests in both stores. It fails closed on missing, duplicate, stale, or foreign
records.

## Dev-lab execution proof

The hardened command was executed on 2026-08-14 inside the existing
`omninode-runtime-effects` container, with its injected Postgres and Memgraph
connections and durable `/app/data` volume. No service restart, Kafka publish,
model call, schema migration, collection creation, or new infrastructure was
used.

- Real `materializer.py` extraction wrote and read back 57 nodes and 100 edges
  in each store at cursor sequence 4 after the final integrity hardening.
- Real `extraction.py` extraction wrote and read back 63 nodes and 104 edges in
  each store without overwriting the first source.
- The final independent read-only audit found 120 distinct nodes and 204
  distinct edges across two current sources in each store. Full parsed node and
  edge payload digests matched between Postgres and Memgraph, with zero
  duplicates, missing fields, cross-source endpoints, or batch/repository
  mismatches.
- An identical replay returned `noop` with the same batch and ID-set digests.
- `inspect` resolved the exact
  `omniintelligence.code_projection.materializer.apply_code_projection` symbol,
  its source span, visibility, three deterministic labels, canonical payload
  digest, and its `defines` edge.
- After the exact namespaced Memgraph label payload for
  `materializer.apply_code_projection` was deliberately replaced with malformed
  JSON, the identical command returned `repair`, reapplied both stores, and
  restored the exact 57-node/100-edge readback and ID-set digests.
- Tombstoning `extraction.py` proved zero source-owned rows/nodes/edges while
  the materializer source remained exactly queryable; re-ingestion restored the
  63-node/104-edge projection at the next cursor sequence.
- The production artifact parser validated both current pointers, all ten
  historical canonical batches, and all six content objects with zero
  unresolved references or unreferenced content.

## Evidence and evolution

`tests/fixtures/code_projection/v1/replay_manifest.json` pins the source,
schema, transform, and batch hashes plus the exact no-network contract test.
`code_projection_batch_v1.schema.sha256` is the portable handoff digest. Tests
rebuild every vector, verify exact bytes, exercise hostile parsing, and prove
duplicate/stale/conflict/replacement/tombstone behavior. They also cover real
extraction, source isolation, artifact integrity, concurrent-operator
serialization, drift repair, live-adapter readback, and command receipts.

Any compatible implementation must validate these serialized vectors without a
cross-package Python import. Any schema, identity, canonicalization, privacy, or
ordering change must add new versioned vectors rather than silently rewriting
v1.
