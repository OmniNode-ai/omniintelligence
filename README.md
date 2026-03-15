# omniintelligence

Intelligence, pattern learning, and code quality analysis as first-class ONEX nodes.

[![CI](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/test.yml/badge.svg)](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/test.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Install

```bash
uv add omninode-intelligence
```

## Minimal Example

```python
from omniintelligence.nodes.intent_classifier.node import NodeIntentClassifier

# All behavior driven by contract YAML
node = NodeIntentClassifier(container=container)
result = await node.execute(input_data)
```

## Key Features

- **Intent classification**: Classify agent prompts into actionable intents
- **Pattern extraction**: Discover recurring patterns from code and events
- **Drift detection**: Detect configuration and behavior drift across repos
- **Code review nodes**: Automated quality assessment with multi-model review
- **Run evaluation**: Evaluate agent run outcomes for continuous improvement
- **21 ONEX nodes**: Following [Four-Node Architecture](https://github.com/OmniNode-ai/omnibase_core/blob/main/docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md)

## Documentation

- [Architecture](docs/architecture/)
- [CLAUDE.md](CLAUDE.md) -- developer context and conventions
- [AGENT.md](AGENT.md) -- LLM navigation guide

## License

[MIT](LICENSE)
