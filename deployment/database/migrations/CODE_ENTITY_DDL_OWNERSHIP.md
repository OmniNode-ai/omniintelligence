# `code_entities` / `code_relationships` DDL does **not** live in this directory

**Ticket:** OMN-15276. **Superseded ticket:** OMN-5765 (closed Done 2026-03-21 claiming
these migrations were reconciled; both conflicting files were still on `dev` four months
later — a false-Done, corrected here with live evidence rather than by reopening).

## What was removed

| File | Origin | Why removed |
| --- | --- | --- |
| `025_code_entities.sql` | OMN-5661 | **Content moved**, unchanged in shape, to the directory the lanes apply. |
| `025_create_code_entities.sql` | OMN-5709 / OMN-5720 | **Rejected shape.** Named the same concepts differently (`name`/`file_path`/`line_start`/`line_end`, `bases`+`decorators` as `JSONB` not `TEXT[]`), carried no `qualified_name`, `signature`, `llm_description` or `last_*_at` stamps, and keyed entity identity on `(source_repo, file_path, name, entity_type)`. Every statement in both live repositories would have raised `UndefinedColumn` against it. |
| `026_create_code_relationships.sql` | OMN-5709 | Conflicting second definition of `code_relationships`; missing `evidence`, `inject_into_context`, `source_repo` and `updated_at`, all of which `RepositoryCodeEntity.upsert_relationship` writes. |
| `027_code_entity_enrichment_part2.sql` | OMN-5676 | Pure `ALTER TABLE code_entities` statements. Folded into the canonical `CREATE TABLE` as native columns; left here it would be an `ALTER` against a table this directory no longer creates, which fails under the runner's `ON_ERROR_STOP=1`. |

The `025` prefix was **triple-claimed** in this directory (`025_code_entities.sql`,
`025_create_code_entities.sql`, `025_review_calibration_runs.sql`). Only
`025_review_calibration_runs.sql` remains, so the prefix is now single-claimed. Nothing
was renumbered: the runners key on the file basename, so renaming an already-applied
migration re-applies its SQL under a new id.

## Where it lives now

**`omnibase_infra/docker/migrations/intelligence/026_create_code_entities.sql`**, with the
full ownership rationale in `omnibase_infra/docker/migrations/intelligence/README.md`.

That directory — not this one — is what every `.201` docker lane applies:
`docker/docker-compose.infra.yml` and `docker-compose.judge.yml` set
`MIGRATIONS_DIR: /migrations/intelligence` and bind-mount
`../docker/migrations/intelligence`, and `scripts/run-intelligence-migrations.sh` globs
`${MIGRATIONS_DIR}/*.sql`.

## Why neither file was ever applied (read-only probe, 2026-07-27T23:46Z)

`omniintelligence.schema_migrations` held **27 identical rows** on the stability-test and
prod lanes, ending at `025_fix_llm_delegation_call_log_date_index`
(2026-06-11T09:37:18Z). No `025_code_entities`, no `025_create_code_entities`, no
`026_create_code_relationships`, no `027_code_entity_enrichment_part2`.
`code_entities` and `code_relationships` were absent from **20/20 databases** across both
lanes.

Because both files were `CREATE TABLE IF NOT EXISTS`, applying them in either order would
never have converged — whichever sorted first silently wins and the other's columns never
appear. The conflict was latent, not loud.

Earlier crawl receipts (OMN-7202, 2026-04-14, "code_entities: 258 rows") were recorded
against a database that no longer carries the table. They are not evidence of
provisioning.

## Consequence for the cloud migrate image

`deployment/docker/Dockerfile.migrate` copies `deployment/database/migrations/*.sql` into
the `omniintelligence-migrate` ECR image used by the cloud k8s migration Job. That image
therefore no longer carries any `code_entities` DDL. Since the table has never existed on
any probed lane, this removes an unapplied file rather than regressing a live schema —
but cloud lanes need either this DDL or a real sync path between the two trees before the
code-intelligence nodes run there. Tracked as a follow-up on OMN-15276; it is explicitly
**not** closed by this change.

`tests/unit/migrations/test_code_entity_ddl_ownership.py` fails if either table's DDL
reappears in this repository.
