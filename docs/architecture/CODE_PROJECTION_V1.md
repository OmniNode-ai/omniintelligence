# Deterministic code projection v1

**Status:** provisional internal A0 seam (OMN-16061)
**Runtime authority:** none
**Workspace authority:** `$OMNI_HOME/docs/standards/OMNINODE_DETERMINISTIC_TRUTH_DOCTRINE.md`

## Decision

`omniintelligence.code_projection` owns a pure, source-scoped serialization
contract for offline code-intelligence proofs. It has no node, contract, topic,
entry point, runtime registration, storage adapter, model call, or network call.
It is not a production ingress path and is not authoritative projected state.

The package remains internal to this lane. A later OmniMemory implementation
must consume the checked-in canonical JSON and schema digest through its own
DTOs; neither product package may import the other. Public export, runtime
activation, or an importer outside this lane triggers the ownership-relocation
gate in the workspace plan.

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

## Endpoint and privacy rules

Every accepted edge endpoint and semantic-document anchor resolves to a node in
the same source-owned batch. A producer must materialize an unresolved symbol
as a deterministic `external_symbol` node or emit a separate typed extraction
diagnostic. Silent relationship drops and foreign-source ownership are invalid.

Raw source and sanitized semantic content live behind distinct
content-addressed artifact references. A batch contains their hashes and refs,
not their bytes. Arbitrary docstrings, evidence strings, source text, vector
bytes, model IDs, local paths, and generic metadata dictionaries are not wire
fields.

## Ordering and replay planning

Only `cursor.sequence`, compared within the same source partition and cursor
authority, orders facts. Source revision and Git SHA are provenance.

The A0 planner is pure and produces change intent for the later A2 reducer:

| Condition | Outcome |
| --- | --- |
| No current manifest or higher incoming sequence | `replace` with exact sorted delete/upsert sets |
| Same sequence and same batch ID | `noop` |
| Same sequence and different batch ID | `conflict` |
| Lower incoming sequence | `stale` |

Different source partitions or cursor authorities are not comparable. A→B→A
at increasing sequences restores A deterministically even when the third source
hash matches the first. The future stateful reducer must apply a batch
atomically and persist its own receipt; A0 does not claim that derived state was
materialized.

## Evidence and evolution

`tests/fixtures/code_projection/v1/replay_manifest.json` pins the source,
schema, transform, and batch hashes plus the exact no-network test command.
`code_projection_batch_v1.schema.sha256` is the portable handoff digest. Tests
rebuild every vector, verify exact bytes, exercise hostile parsing, and prove
duplicate/stale/conflict/replacement/tombstone behavior.

Any compatible implementation must validate these serialized vectors without a
cross-package Python import. Any schema, identity, canonicalization, privacy, or
ordering change must add new versioned vectors rather than silently rewriting
v1.
