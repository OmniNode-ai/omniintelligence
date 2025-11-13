"""
Language-Aware Entity Extractor for LangExtract Service

Advanced entity extraction engine that understands programming languages,
natural languages, and document structures with semantic awareness.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from models.extraction_models import (
    ConfidenceLevel,
    EnhancedEntity,
    EntityMetadata,
    EntityType,
    ExtractionOptions,
    LanguageCode,
    LanguageExtractionResult,
)

logger = logging.getLogger(__name__)


class LanguageAwareExtractor:
    """
    Advanced language-aware entity extractor that combines AST parsing,
    pattern matching, and semantic analysis for comprehensive extraction.
    """

    def __init__(self):
        """Initialize the language-aware extractor"""
        self.supported_languages = {
            # Programming languages
            ".py": LanguageCode.ENGLISH,  # Default to English for code
            ".js": LanguageCode.ENGLISH,
            ".ts": LanguageCode.ENGLISH,
            ".java": LanguageCode.ENGLISH,
            ".cpp": LanguageCode.ENGLISH,
            ".c": LanguageCode.ENGLISH,
            ".go": LanguageCode.ENGLISH,
            ".rs": LanguageCode.ENGLISH,
            ".rb": LanguageCode.ENGLISH,
            ".php": LanguageCode.ENGLISH,
            # Documentation formats
            ".md": LanguageCode.AUTO_DETECT,
            ".rst": LanguageCode.AUTO_DETECT,
            ".txt": LanguageCode.AUTO_DETECT,
            ".html": LanguageCode.AUTO_DETECT,
            ".xml": LanguageCode.AUTO_DETECT,
        }

        # Language detection patterns
        self.language_patterns = {
            LanguageCode.ENGLISH: [
                r"\b(the|and|or|but|in|on|at|to|for|of|with|by)\b",
                r"\b(function|class|method|variable|return|import)\b",
                r"\b(documentation|example|tutorial|guide|reference)\b",
            ],
            LanguageCode.SPANISH: [
                r"\b(el|la|los|las|y|o|pero|en|con|de|por|para)\b",
                r"\b(función|clase|método|variable|documentación)\b",
            ],
            LanguageCode.FRENCH: [
                r"\b(le|la|les|et|ou|mais|dans|avec|de|par|pour)\b",
                r"\b(fonction|classe|méthode|variable|documentation)\b",
            ],
            LanguageCode.GERMAN: [
                r"\b(der|die|das|und|oder|aber|in|mit|von|für)\b",
                r"\b(funktion|klasse|methode|variable|dokumentation)\b",
            ],
        }

        # Programming language specific patterns
        self.code_patterns = {
            "python": {
                "class": r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?:",
                "function": r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\):",
                "variable": r"([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)",
                "import": r"(?:from\s+[\w.]+\s+)?import\s+([\w.,\s*]+)",
                "decorator": r"@([A-Za-z_][A-Za-z0-9_.]*)",
                "constant": r"([A-Z_][A-Z0-9_]*)\s*=",
            },
            "javascript": {
                "class": r"class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
                "function": r"(?:function\s+([A-Za-z_$][A-Za-z0-9_$]*)|([A-Za-z_$][A-Za-z0-9_$]*)\s*[:=]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
                "variable": r"(?:var|let|const)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
                "import": r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
                "export": r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
            },
        }

        # Documentation patterns
        self.doc_patterns = {
            "markdown": {
                "heading": r"^(#{1,6})\s+(.+)$",
                "code_block": r"```(\w+)?\n(.*?)```",
                "link": r"\[([^\]]+)\]\(([^)]+)\)",
                "emphasis": r"[*_]{1,2}([^*_]+)[*_]{1,2}",
                "list_item": r"^[\s]*[-*+]\s+(.+)$",
                "numbered_item": r"^[\s]*\d+\.\s+(.+)$",
            },
            "restructuredtext": {
                "heading": r'^(.+)\n[=\-~`#"^]+$',
                "directive": r"^\.\.\s+(\w+)::\s*(.*?)$",
                "role": r":(\w+):`([^`]+)`",
            },
        }

        # Statistics tracking
        self.stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "total_entities_extracted": 0,
            "average_extraction_time": 0.0,
            "language_distribution": {},
        }

    async def extract_entities(
        self,
        content: str,
        document_path: str,
        extraction_options: ExtractionOptions,
    ) -> LanguageExtractionResult:
        """
        Extract entities from content with language awareness.

        Args:
            content: Source content to analyze
            document_path: Path to source document
            extraction_options: Extraction configuration options

        Returns:
            LanguageExtractionResult with extracted entities and metadata
        """
        start_time = datetime.utcnow()

        try:
            logger.debug(f"Starting language-aware extraction for: {document_path}")

            # Detect primary language
            detected_language = await self._detect_language(content, document_path)
            secondary_languages = await self._detect_secondary_languages(content)

            # Determine extraction strategy based on file type and language
            file_extension = Path(document_path).suffix.lower()
            extraction_strategy = self._determine_extraction_strategy(
                file_extension, detected_language, extraction_options
            )

            # Extract entities using appropriate strategy
            entities = []

            if extraction_strategy == "code":
                entities.extend(
                    await self._extract_code_entities(
                        content, document_path, detected_language, extraction_options
                    )
                )
            elif extraction_strategy == "documentation":
                entities.extend(
                    await self._extract_documentation_entities(
                        content, document_path, detected_language, extraction_options
                    )
                )
            elif extraction_strategy == "multilingual":
                entities.extend(
                    await self._extract_multilingual_entities(
                        content,
                        document_path,
                        detected_language,
                        secondary_languages,
                        extraction_options,
                    )
                )
            else:
                # Hybrid approach
                entities.extend(
                    await self._extract_hybrid_entities(
                        content, document_path, detected_language, extraction_options
                    )
                )

            # Apply quality filtering
            filtered_entities = await self._filter_entities_by_quality(
                entities, extraction_options
            )

            # Calculate metrics
            extraction_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            confidence_score = self._calculate_extraction_confidence(filtered_entities)
            language_confidence = self._calculate_language_confidence(
                detected_language, content
            )

            # Update statistics
            self._update_statistics(True, len(filtered_entities), extraction_time)

            # Create result
            result = LanguageExtractionResult(
                entities=filtered_entities,
                language_detected=detected_language,
                confidence_score=confidence_score,
                language_confidence=language_confidence,
                multilingual_detected=len(secondary_languages) > 0,
                primary_language=detected_language,
                secondary_languages=secondary_languages,
                processing_time_ms=extraction_time,
                total_tokens=len(content.split()) if content else 0,
            )

            logger.debug(
                f"Extraction completed: {len(filtered_entities)} entities, {extraction_time:.2f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"Language-aware extraction failed for {document_path}: {e}")
            self._update_statistics(False, 0, 0)

            # Return empty result on failure
            return LanguageExtractionResult(
                entities=[],
                language_detected=LanguageCode.ENGLISH,
                confidence_score=0.0,
                language_confidence=0.0,
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds()
                * 1000,
            )

    async def _detect_language(self, content: str, document_path: str) -> LanguageCode:
        """Detect the primary language of the content"""
        try:
            # Check file extension first
            file_extension = Path(document_path).suffix.lower()
            if file_extension in self.supported_languages:
                suggested_lang = self.supported_languages[file_extension]
                if suggested_lang != LanguageCode.AUTO_DETECT:
                    return suggested_lang

            # Perform pattern-based language detection
            language_scores = {}

            for language, patterns in self.language_patterns.items():
                score = 0
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    score += len(matches)

                if score > 0:
                    language_scores[language] = score / len(content.split())

            # Return language with highest score
            if language_scores:
                detected_language = max(language_scores, key=language_scores.get)
                return detected_language

            # Default to English
            return LanguageCode.ENGLISH

        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return LanguageCode.ENGLISH

    async def _detect_secondary_languages(self, content: str) -> List[LanguageCode]:
        """Detect secondary languages in multilingual content"""
        try:
            secondary_languages = []

            # Simple heuristic: look for language indicators
            language_indicators = {
                LanguageCode.SPANISH: [r"\b(español|spanish|es-)\b", r"[ñáéíóúü]"],
                LanguageCode.FRENCH: [
                    r"\b(français|french|fr-)\b",
                    r"[àâäéèêëïîôùûüÿç]",
                ],
                LanguageCode.GERMAN: [r"\b(deutsch|german|de-)\b", r"[äöüß]"],
                LanguageCode.CHINESE: [r"[\u4e00-\u9fff]"],
                LanguageCode.JAPANESE: [r"[\u3040-\u309f\u30a0-\u30ff]"],
                LanguageCode.KOREAN: [r"[\uac00-\ud7af]"],
                LanguageCode.ARABIC: [r"[\u0600-\u06ff]"],
                LanguageCode.RUSSIAN: [r"[\u0400-\u04ff]"],
            }

            for language, indicators in language_indicators.items():
                for indicator in indicators:
                    if re.search(indicator, content, re.IGNORECASE):
                        secondary_languages.append(language)
                        break

            return secondary_languages

        except Exception as e:
            logger.warning(f"Secondary language detection failed: {e}")
            return []

    def _determine_extraction_strategy(
        self,
        file_extension: str,
        detected_language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> str:
        """Determine the best extraction strategy for the content"""

        # Code files
        if file_extension in [
            ".py",
            ".js",
            ".ts",
            ".java",
            ".cpp",
            ".c",
            ".go",
            ".rs",
            ".rb",
            ".php",
        ]:
            return "code"

        # Documentation files
        elif file_extension in [".md", ".rst", ".txt"]:
            return "documentation"

        # Multilingual content
        elif (
            extraction_options.enable_multilingual
            and detected_language != LanguageCode.ENGLISH
        ):
            return "multilingual"

        # Default to hybrid approach
        else:
            return "hybrid"

    async def _extract_code_entities(
        self,
        content: str,
        document_path: str,
        language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract entities from programming code"""
        entities = []

        try:
            # Determine programming language from file extension
            file_extension = Path(document_path).suffix.lower()
            prog_language = file_extension[1:]  # Remove the dot

            if prog_language in self.code_patterns:
                patterns = self.code_patterns[prog_language]
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("//"):
                        continue

                    # Extract different types of code entities
                    for entity_type, pattern in patterns.items():
                        matches = re.finditer(pattern, line)

                        for match in matches:
                            entity_name = (
                                match.group(1) or match.group(2)
                                if match.lastindex and match.lastindex >= 2
                                else match.group(1)
                            )
                            if entity_name and entity_name.strip():
                                entity = await self._create_code_entity(
                                    entity_name.strip(),
                                    entity_type,
                                    document_path,
                                    line_num,
                                    line,
                                    language,
                                )
                                entities.append(entity)

            logger.debug(
                f"Extracted {len(entities)} code entities from {document_path}"
            )
            return entities

        except Exception as e:
            logger.error(f"Code entity extraction failed: {e}")
            return []

    async def _extract_documentation_entities(
        self,
        content: str,
        document_path: str,
        language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract entities from documentation content"""
        entities = []

        try:
            file_extension = Path(document_path).suffix.lower()
            doc_format = file_extension[1:]  # Remove the dot

            if doc_format in self.doc_patterns:
                patterns = self.doc_patterns[doc_format]
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Extract documentation entities
                    for entity_type, pattern in patterns.items():
                        if entity_type == "code_block":
                            # Handle multi-line code blocks separately
                            continue

                        matches = re.finditer(pattern, line, re.MULTILINE)

                        for match in matches:
                            if entity_type == "heading":
                                level = len(match.group(1)) if match.group(1) else 1
                                title = (
                                    match.group(2)
                                    if match.lastindex >= 2
                                    else match.group(1)
                                )

                                entity = await self._create_documentation_entity(
                                    title.strip(),
                                    EntityType.CONCEPT,
                                    document_path,
                                    line_num,
                                    line,
                                    language,
                                    {"heading_level": level},
                                )
                                entities.append(entity)

                            elif entity_type == "link":
                                link_text = match.group(1)
                                link_url = match.group(2)

                                entity = await self._create_documentation_entity(
                                    link_text,
                                    EntityType.CONCEPT,
                                    document_path,
                                    line_num,
                                    line,
                                    language,
                                    {"link_url": link_url, "link_type": "reference"},
                                )
                                entities.append(entity)

            # Handle code blocks separately
            await self._extract_code_blocks_from_docs(
                content, document_path, entities, language
            )

            logger.debug(
                f"Extracted {len(entities)} documentation entities from {document_path}"
            )
            return entities

        except Exception as e:
            logger.error(f"Documentation entity extraction failed: {e}")
            return []

    async def _extract_multilingual_entities(
        self,
        content: str,
        document_path: str,
        primary_language: LanguageCode,
        secondary_languages: List[LanguageCode],
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract entities from multilingual content"""
        entities = []

        try:
            # Extract entities for each detected language
            all_languages = [primary_language] + secondary_languages

            for language in all_languages:
                # Apply language-specific extraction patterns
                lang_entities = await self._extract_language_specific_entities(
                    content, document_path, language, extraction_options
                )
                entities.extend(lang_entities)

            # Remove duplicates and merge similar entities
            entities = await self._merge_multilingual_entities(entities)

            logger.debug(
                f"Extracted {len(entities)} multilingual entities from {document_path}"
            )
            return entities

        except Exception as e:
            logger.error(f"Multilingual entity extraction failed: {e}")
            return []

    async def _extract_hybrid_entities(
        self,
        content: str,
        document_path: str,
        language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract entities using hybrid approach combining multiple strategies"""
        entities = []

        try:
            # Try code extraction first
            if extraction_options.extract_code_patterns:
                code_entities = await self._extract_code_entities(
                    content, document_path, language, extraction_options
                )
                entities.extend(code_entities)

            # Try documentation extraction
            if extraction_options.extract_documentation_concepts:
                doc_entities = await self._extract_documentation_entities(
                    content, document_path, language, extraction_options
                )
                entities.extend(doc_entities)

            # Extract general concepts and keywords
            concept_entities = await self._extract_general_concepts(
                content, document_path, language, extraction_options
            )
            entities.extend(concept_entities)

            logger.debug(
                f"Extracted {len(entities)} hybrid entities from {document_path}"
            )
            return entities

        except Exception as e:
            logger.error(f"Hybrid entity extraction failed: {e}")
            return []

    async def _create_code_entity(
        self,
        name: str,
        entity_type: str,
        document_path: str,
        line_number: int,
        source_line: str,
        language: LanguageCode,
    ) -> EnhancedEntity:
        """Create a code entity with appropriate metadata"""

        # Map entity type strings to EntityType enum
        type_mapping = {
            "class": EntityType.CLASS,
            "function": EntityType.FUNCTION,
            "method": EntityType.METHOD,
            "variable": EntityType.VARIABLE,
            "constant": EntityType.CONSTANT,
            "import": EntityType.MODULE,
            "export": EntityType.MODULE,
            "decorator": EntityType.FUNCTION,
        }

        mapped_type = type_mapping.get(entity_type, EntityType.CONCEPT)

        # Calculate confidence based on entity type and context
        confidence = self._calculate_entity_confidence(name, entity_type, source_line)

        # Create metadata
        metadata = EntityMetadata(
            extraction_method="language_aware_code_extraction",
            confidence_level=self._confidence_to_level(confidence),
            language_detected=language,
            source_line_start=line_number,
            source_line_end=line_number,
        )

        return EnhancedEntity(
            entity_id=f"code_{hash(f'{document_path}:{line_number}:{name}') % 100000:05d}",
            name=name,
            entity_type=mapped_type,
            description=f"{entity_type.title()}: {name}",
            confidence_score=confidence,
            source_path=document_path,
            language=language,
            properties={
                "entity_subtype": entity_type,
                "source_line": source_line.strip(),
                "programming_language": Path(document_path).suffix[1:],
            },
            metadata=metadata,
        )

    async def _create_documentation_entity(
        self,
        name: str,
        entity_type: EntityType,
        document_path: str,
        line_number: int,
        source_line: str,
        language: LanguageCode,
        properties: Dict[str, Any],
    ) -> EnhancedEntity:
        """Create a documentation entity with appropriate metadata"""

        confidence = self._calculate_entity_confidence(
            name, "documentation", source_line
        )

        metadata = EntityMetadata(
            extraction_method="language_aware_documentation_extraction",
            confidence_level=self._confidence_to_level(confidence),
            language_detected=language,
            source_line_start=line_number,
            source_line_end=line_number,
        )

        return EnhancedEntity(
            entity_id=f"doc_{hash(f'{document_path}:{line_number}:{name}') % 100000:05d}",
            name=name,
            entity_type=entity_type,
            description=f"Documentation concept: {name}",
            confidence_score=confidence,
            source_path=document_path,
            language=language,
            properties=properties,
            metadata=metadata,
        )

    async def _extract_code_blocks_from_docs(
        self,
        content: str,
        document_path: str,
        entities: List[EnhancedEntity],
        language: LanguageCode,
    ):
        """Extract code blocks from documentation"""
        try:
            # Find code blocks in markdown-style format
            code_block_pattern = r"```(\w+)?\n(.*?)```"
            matches = re.finditer(code_block_pattern, content, re.DOTALL)

            for match in matches:
                code_language = match.group(1) or "unknown"
                code_content = match.group(2).strip()

                if code_content:
                    entity = EnhancedEntity(
                        entity_id=f"codeblock_{hash(code_content[:100]) % 100000:05d}",
                        name=f"Code Block ({code_language})",
                        entity_type=EntityType.EXAMPLE,
                        description=f"Code example in {code_language}",
                        content=code_content,
                        confidence_score=0.8,
                        source_path=document_path,
                        language=language,
                        properties={
                            "code_language": code_language,
                            "code_type": "example",
                            "lines_of_code": len(code_content.split("\n")),
                        },
                        metadata=EntityMetadata(
                            extraction_method="code_block_extraction",
                            confidence_level=ConfidenceLevel.HIGH,
                            language_detected=language,
                        ),
                    )
                    entities.append(entity)

        except Exception as e:
            logger.warning(f"Code block extraction failed: {e}")

    async def _extract_general_concepts(
        self,
        content: str,
        document_path: str,
        language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract general concepts and keywords"""
        entities = []

        try:
            # Extract capitalized words as potential concepts
            concept_pattern = r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)*)\b"
            matches = re.findall(concept_pattern, content)

            # Count frequency and create entities for common concepts
            concept_freq = {}
            for concept in matches:
                concept_freq[concept] = concept_freq.get(concept, 0) + 1

            # Create entities for concepts that appear multiple times
            for concept, frequency in concept_freq.items():
                if (
                    frequency >= 2 and len(concept) > 3
                ):  # Filter by frequency and length
                    confidence = min(
                        0.9, 0.3 + (frequency * 0.1)
                    )  # Higher frequency = higher confidence

                    entity = EnhancedEntity(
                        entity_id=f"concept_{hash(f'{document_path}:{concept}') % 100000:05d}",
                        name=concept,
                        entity_type=EntityType.CONCEPT,
                        description=f"Concept: {concept}",
                        confidence_score=confidence,
                        source_path=document_path,
                        language=language,
                        properties={
                            "frequency": frequency,
                            "concept_type": "general",
                        },
                        metadata=EntityMetadata(
                            extraction_method="general_concept_extraction",
                            confidence_level=self._confidence_to_level(confidence),
                            language_detected=language,
                        ),
                    )
                    entities.append(entity)

            return entities

        except Exception as e:
            logger.error(f"General concept extraction failed: {e}")
            return []

    async def _extract_language_specific_entities(
        self,
        content: str,
        document_path: str,
        language: LanguageCode,
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Extract entities specific to a particular language"""
        entities = []

        try:
            # This would contain language-specific extraction logic
            # For now, implement basic keyword extraction

            if language in self.language_patterns:
                patterns = self.language_patterns[language]

                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)

                    for match in matches:
                        if len(match) > 2:  # Filter short matches
                            entity = EnhancedEntity(
                                entity_id=f"lang_{language}_{hash(match) % 100000:05d}",
                                name=match,
                                entity_type=EntityType.KEYWORD,
                                description=f"{language} keyword: {match}",
                                confidence_score=0.6,
                                source_path=document_path,
                                language=language,
                                properties={
                                    "language_specific": True,
                                    "keyword_type": "linguistic",
                                },
                                metadata=EntityMetadata(
                                    extraction_method="language_specific_extraction",
                                    confidence_level=ConfidenceLevel.MEDIUM,
                                    language_detected=language,
                                ),
                            )
                            entities.append(entity)

            return entities

        except Exception as e:
            logger.error(f"Language-specific extraction failed for {language}: {e}")
            return []

    async def _filter_entities_by_quality(
        self,
        entities: List[EnhancedEntity],
        extraction_options: ExtractionOptions,
    ) -> List[EnhancedEntity]:
        """Filter entities based on quality thresholds"""
        filtered_entities = []

        for entity in entities:
            # Apply confidence threshold
            if entity.confidence_score < extraction_options.min_confidence_threshold:
                continue

            # Apply quality threshold if available
            if (
                entity.quality_score is not None
                and entity.quality_score < extraction_options.min_quality_threshold
            ):
                continue

            # Apply entity type filter if specified
            if (
                extraction_options.expected_entity_types
                and entity.entity_type not in extraction_options.expected_entity_types
            ):
                continue

            # Apply max entities per type limit
            if extraction_options.max_entities_per_type:
                type_count = len(
                    [
                        e
                        for e in filtered_entities
                        if e.entity_type == entity.entity_type
                    ]
                )
                if type_count >= extraction_options.max_entities_per_type:
                    continue

            filtered_entities.append(entity)

        return filtered_entities

    async def _merge_multilingual_entities(
        self, entities: List[EnhancedEntity]
    ) -> List[EnhancedEntity]:
        """Merge similar entities from different languages"""
        # Simple implementation - could be enhanced with semantic similarity
        merged_entities = []
        processed_names = set()

        for entity in entities:
            normalized_name = entity.name.lower().strip()

            if normalized_name not in processed_names:
                merged_entities.append(entity)
                processed_names.add(normalized_name)

        return merged_entities

    def _calculate_entity_confidence(
        self, name: str, entity_type: str, context: str
    ) -> float:
        """Calculate confidence score for an entity"""
        confidence = 0.5  # Base confidence

        # Increase confidence for longer, more descriptive names
        if len(name) > 3:
            confidence += 0.1
        if len(name) > 10:
            confidence += 0.1

        # Increase confidence based on entity type
        type_confidence = {
            "class": 0.2,
            "function": 0.2,
            "method": 0.15,
            "variable": 0.1,
            "constant": 0.15,
            "documentation": 0.1,
        }
        confidence += type_confidence.get(entity_type, 0.05)

        # Decrease confidence for very common words
        common_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        if name.lower() in common_words:
            confidence -= 0.3

        return min(1.0, max(0.0, confidence))

    def _calculate_extraction_confidence(self, entities: List[EnhancedEntity]) -> float:
        """Calculate overall extraction confidence"""
        if not entities:
            return 0.0

        total_confidence = sum(entity.confidence_score for entity in entities)
        return total_confidence / len(entities)

    def _calculate_language_confidence(
        self, detected_language: LanguageCode, content: str
    ) -> float:
        """Calculate confidence in language detection"""
        if detected_language == LanguageCode.ENGLISH:
            return 0.8  # Default high confidence for English

        # Calculate based on pattern matches
        patterns = self.language_patterns.get(detected_language, [])
        if not patterns:
            return 0.5

        match_count = 0
        total_words = len(content.split())

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            match_count += len(matches)

        if total_words == 0:
            return 0.5

        return min(1.0, match_count / total_words * 10)  # Scale factor

    def _confidence_to_level(self, confidence: float) -> ConfidenceLevel:
        """Convert confidence score to confidence level"""
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.4:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _update_statistics(
        self, success: bool, entity_count: int, extraction_time: float
    ):
        """Update extraction statistics"""
        self.stats["total_extractions"] += 1

        if success:
            self.stats["successful_extractions"] += 1
            self.stats["total_entities_extracted"] += entity_count

            # Update average extraction time
            total_time = self.stats["average_extraction_time"] * (
                self.stats["successful_extractions"] - 1
            )
            total_time += extraction_time
            self.stats["average_extraction_time"] = (
                total_time / self.stats["successful_extractions"]
            )
        else:
            self.stats["failed_extractions"] += 1

    async def get_statistics(self) -> Dict[str, Any]:
        """Get extractor statistics"""
        success_rate = 0.0
        if self.stats["total_extractions"] > 0:
            success_rate = (
                self.stats["successful_extractions"] / self.stats["total_extractions"]
            )

        return {
            "extractor_type": "language_aware",
            "total_extractions": self.stats["total_extractions"],
            "successful_extractions": self.stats["successful_extractions"],
            "failed_extractions": self.stats["failed_extractions"],
            "success_rate": success_rate,
            "total_entities_extracted": self.stats["total_entities_extracted"],
            "average_extraction_time_ms": self.stats["average_extraction_time"],
            "average_entities_per_extraction": (
                self.stats["total_entities_extracted"]
                / max(self.stats["successful_extractions"], 1)
            ),
            "supported_languages": list(self.supported_languages.keys()),
            "supported_code_languages": list(self.code_patterns.keys()),
            "supported_doc_formats": list(self.doc_patterns.keys()),
        }
