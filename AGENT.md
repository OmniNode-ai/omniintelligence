# AGENT.md -- omniintelligence

> LLM navigation guide. Points to context sources -- does not duplicate them.

## Context

- **Node inventory**: `README.md` (node table)
- **Architecture**: `docs/architecture/`
- **Conventions**: `CLAUDE.md`

## Commands

- Tests: `uv run pytest -m unit`
- Lint: `uv run ruff check src/ tests/`
- Type check: `uv run mypy src/omniintelligence/`
- Pre-commit: `pre-commit run --all-files`

## Cross-Repo

- Shared platform standards: `~/.claude/CLAUDE.md`
- Core models: `omnibase_core/CLAUDE.md`
- SPI protocols: `omnibase_spi/CLAUDE.md`

## Rules

- All nodes follow ONEX 4-node architecture
- Intelligence events published via Kafka event bus
- Pattern storage in Qdrant vector database
