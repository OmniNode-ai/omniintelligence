# Code projection v1 replay vectors

These OMN-16061 fixtures freeze the offline, source-scoped serialization seam
between later OmniIntelligence artifact work and later OmniMemory projection
work. They are proof vectors, not a production ingestion event, node, topic, or
runtime route.

The authoritative batch files contain metadata and content-addressed artifact
references only. Raw Python/TypeScript source and sanitized semantic text remain
separate fixture artifacts; neither is inlined into a batch. Every batch uses
compact, key-sorted UTF-8/NFC JSON framed by exactly one LF byte.

`replay_manifest.json` pins the base commit, source and output hashes, schema
digest, contract versions, replay scenarios, no-network assertion, and exact
focused test command. `code_projection_batch_v1.schema.sha256` is the portable
schema-digest handoff for the later independent OmniMemory DTO implementation.

The A→B→A vectors use increasing source-partition cursors. Source revision and
Git identity remain provenance and never determine reducer order. The empty
source is a successful empty snapshot; deletion and policy revocation are
separate explicit tombstone batches.

Contract YAML is configuration input only in A0. These vectors make no claim
that Markdown/YAML content ingestion, live extraction adapters, storage,
brokers, models, or production routing exist.
