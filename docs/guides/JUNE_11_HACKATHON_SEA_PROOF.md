> **Navigation**: [Home](../INDEX.md) > [Guides](.) > June 11 Hackathon SEA Proof

# June 11 Hackathon SEA Proof

This guide defines the OmniIntelligence SEA proof boundary for the June 11 hackathon demo and judge reproduction lane.

## Scope

OmniIntelligence owns the intelligence-side SEA surfaces:

- evaluation and review nodes;
- plan multi-model review orchestration;
- routing feedback and cost forecast computation;
- pattern, document, and quality-analysis events consumed by downstream projections;
- contracts that declare node subscriptions and publish topics.

It does not own runtime infrastructure, dashboard rendering, deployment promotion, model-key storage, or projection table DDL. Those are owned by `omnibase_infra`, `omnidash`, `onex_change_control`, and the relevant runtime/secret systems.

## Accepted Proof Boundary

An accepted SEA proof packet must be fresh. Historical rows can be regression anchors, but they cannot satisfy June 11 acceptance.

Each accepted SEA leg records:

- runtime SHA;
- image digest;
- contract hash;
- overlay hash;
- correlation ID;
- provider;
- model;
- endpoint_ref;
- resolved endpoint;
- route source;
- terminal event;
- projection row;
- projection API response;
- dashboard screenshot;
- browser network trace;
- replay class.

The packet is accepted only when `provider`, `model`, `endpoint_ref`, and resolved endpoint are proven to originate from contract, overlay, or routing authority. Hardcoded literals, provider-specific fallback strings, environment-variable routing, and endpoint string rewrites are not accepted proof authority.

## Judge Reproduction Lane

Judge reproduction must run from overlays and secret references, not source edits or hidden local state.

The judge lane records the same route fields as the demo packet:

- provider;
- model;
- endpoint_ref;
- route source;
- terminal event;
- replay class.

Environment variables are acceptable only for secret values or bootstrap pointers. They are not accepted as endpoint, mode, topic, provider, model, or data-source authority for proof packets.

## Dashboard Evidence Boundary

Dashboard nonblank state is not proof by itself. Every demo-visible panel that uses OmniIntelligence data must be classified as one of:

- `projection-backed`;
- `runtime-observed`;
- `degraded`;
- `hidden`.

Accepted screenshots must be paired with browser network traces. A screenshot without the matching network trace is presentation evidence, not proof evidence.

## Topic And Projection Authority

Topic existence and route attachment are separate claims.

Topic auto-creation proves only that the topic exists. It does not prove:

- a runtime consumer is attached;
- a dispatcher route exists;
- the handler executes;
- a terminal event is emitted;
- a projection row is materialized.

Projection API exposure also does not create tables or views. Accepted projection proof must identify the materialization authority and the producer/consumer responsible for the row used in the packet.

## Fallback Classification

If live Gemini proof is unavailable, classify the SEA leg explicitly:

- `blocked_by_credential_authority`;
- `blocked_by_runtime_registration`;
- `blocked_by_projection_authority`;
- `blocked_by_dashboard_authority`;
- `degraded_with_recorded_flash_lite_evidence`.

Fallback evidence must still include the local runtime spine, correlation ID, terminal event, and replay classification.

## Operational Boundary

Thursday morning work may include dry-run, recording, submission, and evidence verification.

It must not include architecture repair, runtime redesign, hidden environment override fixes, or dashboard data-source rewrites unless a separate ticket and proof path already exists.
