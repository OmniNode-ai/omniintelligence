# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Multi-language entity extraction using regex patterns.

Ported from Archive/omniarchon LanguageAwareExtractor. Extracts structural
entities from TypeScript, JavaScript, and other languages using configurable
regex patterns from contract YAML.

Python files continue using Part 1's AST handler. This handler is for
non-Python languages only.

Type normalization: TS `interface` → "interface", `type` → "type_alias",
`enum` → "enum" (not silently mapped to "class").

Confidence: regex-extracted entities get 0.7 (lower than AST's 1.0).

Reference: OMN-5679
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Confidence for regex-extracted entities (lower than AST = 1.0)
REGEX_CONFIDENCE = 0.7


class MultiLangExtractor:
    """Extracts code entities from non-Python files using regex patterns.

    All patterns are read from contract config's language_extractors section.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize from contract config.

        Args:
            config: The ``config.language_extractors`` dict.
        """
        self._languages: dict[str, dict[str, Any]] = {}
        for lang_name, lang_config in config.items():
            if isinstance(lang_config, dict) and lang_config.get("enabled", False):
                if lang_config.get("strategy") == "regex":
                    self._languages[lang_name] = lang_config

    def get_language_for_extension(self, extension: str) -> str | None:
        """Map file extension to language name."""
        ext_map = {
            "ts": "typescript",
            "tsx": "typescript",
            "js": "javascript",
            "jsx": "javascript",
            "go": "go",
        }
        return ext_map.get(extension)

    def can_extract(self, extension: str) -> bool:
        """Return True if this extractor handles the given file extension."""
        lang = self.get_language_for_extension(extension)
        return lang is not None and lang in self._languages

    def extract(
        self,
        *,
        source_content: str,
        source_path: str,
        source_repo: str,
        file_hash: str,
        extension: str,
    ) -> list[dict[str, Any]]:
        """Extract entities from a non-Python source file.

        Returns list of entity dicts compatible with ModelCodeEntity fields.
        """
        lang = self.get_language_for_extension(extension)
        if not lang or lang not in self._languages:
            return []

        lang_config = self._languages[lang]
        patterns = lang_config.get("patterns", {})
        entities: list[dict[str, Any]] = []

        for entity_type, pattern_str in patterns.items():
            if not pattern_str:
                continue

            # Map pattern names to normalized entity types
            normalized_type = self._normalize_entity_type(entity_type)

            try:
                for match in re.finditer(pattern_str, source_content, re.MULTILINE):
                    name = (
                        match.group(1)
                        if match.lastindex and match.lastindex >= 1
                        else None
                    )
                    if not name:
                        continue

                    line_number = source_content[: match.start()].count("\n") + 1

                    # Extract bases for class/interface inheritance
                    bases: list[str] = []
                    if match.lastindex and match.lastindex >= 2:
                        base = match.group(2)
                        if base:
                            bases = [base]

                    # Build qualified name
                    module_path = source_path.replace("/", ".").rsplit(".", 1)[0]
                    qualified_name = f"{module_path}.{name}"

                    entities.append(
                        {
                            "id": str(uuid4()),
                            "entity_name": name,
                            "entity_type": normalized_type,
                            "qualified_name": qualified_name,
                            "source_repo": source_repo,
                            "source_path": source_path,
                            "line_number": line_number,
                            "bases": bases,
                            "methods": [],
                            "fields": [],
                            "decorators": [],
                            "docstring": None,
                            "signature": None,
                            "file_hash": file_hash,
                            "source_language": lang,
                            "confidence": REGEX_CONFIDENCE,
                        }
                    )
            except re.error as exc:
                logger.warning("Invalid regex for %s.%s: %s", lang, entity_type, exc)

        return entities

    @staticmethod
    def _normalize_entity_type(pattern_name: str) -> str:
        """Map pattern name to normalized entity type."""
        type_map = {
            "class": "class",
            "function": "function",
            "arrow_function": "function",
            "interface": "interface",
            "type_alias": "type_alias",
            "import": "import",
            "enum": "enum",
            "struct": "struct",
        }
        return type_map.get(pattern_name, pattern_name)
