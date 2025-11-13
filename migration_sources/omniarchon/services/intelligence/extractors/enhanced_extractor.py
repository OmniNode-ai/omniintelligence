"""
Enhanced Entity Extractor for Archon Intelligence Service

Advanced entity extraction with semantic analysis, embeddings, and pattern recognition.
Based on omnibase_3 LangExtract patterns adapted for Archon's requirements.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from extractors.base_extractor import BaseEntityExtractor
from models.entity_models import (
    EntityType,
    KnowledgeEntity,
    PatternMatch,
)
from scoring.quality_scorer import QualityScorer
from src.utils.rate_limiter import EmbeddingRateLimiter

logger = logging.getLogger(__name__)


class EnhancedEntityExtractor(BaseEntityExtractor):
    """
    Enhanced entity extractor with semantic analysis capabilities.

    Combines AST parsing with embedding-based semantic analysis,
    pattern recognition, and quality scoring for comprehensive
    entity extraction and relationship detection.
    """

    def __init__(
        self,
        memgraph_adapter=None,
        embedding_model_url: str = "http://192.168.86.201:8002",
    ):
        """Initialize enhanced extractor with semantic analysis capabilities"""
        import os

        super().__init__()

        self.memgraph_adapter = memgraph_adapter
        self.embedding_model_url = embedding_model_url.rstrip("/")
        self.quality_scorer = QualityScorer()

        # Embedding model configuration - read from environment
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
        )
        self.embedding_dimension = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

        # HTTP client for vLLM API calls with connection pooling
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                30.0, connect=5.0
            ),  # Increased to 30s total, 5s connect
            limits=httpx.Limits(
                max_connections=100,  # Support up to 100 parallel requests
                max_keepalive_connections=20,  # Keep more connections alive
            ),
            http2=True,  # Enable HTTP/2 for better multiplexing
        )

        # Rate limiter for embedding requests - prevents queue buildup at vLLM
        # Default: 3 concurrent requests per consumer
        # Can be tuned to 5-10 based on vLLM service capacity
        # Formula: N consumers × max_concurrent = total concurrent load
        max_concurrent = int(os.getenv("EMBEDDING_MAX_CONCURRENT", "3"))
        self.rate_limiter = EmbeddingRateLimiter(max_concurrent=max_concurrent)
        logger.info(
            f"📊 Embedding rate limiter configured: max_concurrent={max_concurrent}"
        )

        # Semantic patterns for enhanced analysis
        self.semantic_patterns = {
            "design_patterns": [
                r"class.*Factory.*:",
                r"class.*Builder.*:",
                r"class.*Observer.*:",
                r"class.*Singleton.*:",
                r"class.*Adapter.*:",
                r"class.*Strategy.*:",
            ],
            "anti_patterns": [
                r"global\s+\w+",
                r"from\s+.*\s+import\s+\*",
                r"except\s*:",
                r"pass\s*$",
            ],
            "code_smells": [
                r"def\s+\w+\([^)]{50,}\)",
                r"if.*and.*and.*and",
                r"elif.*elif.*elif.*elif",
            ],
            "api_endpoints": [
                r"@app\.(get|post|put|delete|patch)",
                r"@router\.(get|post|put|delete|patch)",
                r"app\.(get|post|put|delete|patch)\(",
            ],
            "database_operations": [
                r"SELECT.*FROM",
                r"INSERT.*INTO",
                r"UPDATE.*SET",
                r"DELETE.*FROM",
                r"CREATE.*TABLE",
            ],
        }

    async def extract_entities_from_document(
        self, content: str, source_path: str, metadata: Dict[str, Any] = None
    ) -> Tuple[List[KnowledgeEntity], List[Dict[str, Any]]]:
        """Extract entities from document content with semantic enhancement and relationships"""

        # Entry logging
        logger.info(
            f"ENTER extract_entities_from_document: source_path={source_path}, "
            f"content_length={len(content)}, has_metadata={metadata is not None}"
        )

        try:
            # Start with base extraction
            entities = self.extract_entities_from_content(content, source_path)

            # Enhance with semantic analysis - parallel execution for massive speedup
            enhancement_tasks = [
                self._enhance_entity_with_semantics(entity, content, metadata or {})
                for entity in entities
            ]

            # Execute in parallel with error handling
            results = await asyncio.gather(*enhancement_tasks, return_exceptions=True)

            # Filter out exceptions, keep successful results
            enhanced_entities = [
                result for result in results if not isinstance(result, Exception)
            ]

            # Log any failures
            failed_count = sum(1 for r in results if isinstance(r, Exception))
            if failed_count > 0:
                logger.warning(
                    f"Failed to enhance {failed_count}/{len(entities)} entities in document"
                )

            # Extract semantic patterns
            pattern_entities = await self._extract_semantic_patterns(
                content, source_path
            )
            enhanced_entities.extend(pattern_entities)

            # Add document-level entity if not exists
            if not any(e.entity_type == EntityType.DOCUMENT for e in enhanced_entities):
                doc_entity = await self._create_document_entity(
                    content, source_path, metadata or {}
                )
                enhanced_entities.append(doc_entity)

            # Extract relationships via LangExtract (always, not just when doc entity is created)
            logger.info(
                f"About to extract relationships | entities_count={len(enhanced_entities)}"
            )
            relationships = await self._extract_relationships_via_langextract(
                content=content, entities=enhanced_entities, metadata=metadata or {}
            )

            # Success exit logging
            logger.info(
                f"EXIT extract_entities_from_document: SUCCESS - entities={len(enhanced_entities)}, "
                f"relationships={len(relationships)}"
            )

            return enhanced_entities, relationships

        except Exception as e:
            logger.error(
                f"EXIT extract_entities_from_document: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            # Return empty tuple on error instead of raising (to prevent unpacking errors)
            logger.warning(
                f"Returning empty tuple due to error in extract_entities_from_document"
            )
            return ([], [])

    async def extract_entities_from_code(
        self,
        content: str,
        source_path: str,
        language: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> List[KnowledgeEntity]:
        """Extract entities from code content with advanced analysis"""

        # Entry logging
        logger.info(
            f"ENTER extract_entities_from_code: source_path={source_path}, "
            f"language={language}, content_length={len(content)}"
        )

        try:
            # Start with base extraction
            entities = self.extract_entities_from_content(
                content, source_path, language
            )

            # Enhance with semantic analysis and quality scoring - parallel execution for massive speedup
            detected_language = language or self._detect_language(source_path)
            enhancement_tasks = [
                self._enhance_code_entity(
                    entity,
                    content,
                    detected_language,
                    metadata or {},
                )
                for entity in entities
            ]

            # Execute in parallel with error handling
            results = await asyncio.gather(*enhancement_tasks, return_exceptions=True)

            # Filter out exceptions, keep successful results
            enhanced_entities = [
                result for result in results if not isinstance(result, Exception)
            ]

            # Log any failures
            failed_count = sum(1 for r in results if isinstance(r, Exception))
            if failed_count > 0:
                logger.warning(
                    f"Failed to enhance {failed_count}/{len(entities)} entities in code"
                )

            # Extract advanced patterns
            pattern_entities = await self._extract_code_patterns(
                content, source_path, language
            )
            enhanced_entities.extend(pattern_entities)

            # Add quality scores
            await self._add_quality_scores(enhanced_entities, content, source_path)

            # Success exit logging
            logger.info(
                f"EXIT extract_entities_from_code: SUCCESS - entities={len(enhanced_entities)}"
            )

            return enhanced_entities

        except Exception as e:
            logger.error(
                f"EXIT extract_entities_from_code: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _extract_relationships_via_langextract(
        self, content: str, entities: List[KnowledgeEntity], metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract relationships by calling LangExtract service"""

        langextract_url = os.getenv(
            "LANGEXTRACT_SERVICE_URL", "http://archon-langextract:8156"
        )

        # Entry logging
        logger.info(
            f"ENTER _extract_relationships_via_langextract: entities={len(entities)}, "
            f"content_length={len(content)}, url={langextract_url}"
        )

        # Convert entities to format expected by RelationshipMapper
        entity_list = [
            {
                "text": entity.name,
                "entity_type": entity.entity_type,
                "confidence_score": entity.confidence_score,
            }
            for entity in entities
        ]

        # Infer document type from source path for better extraction
        document_type = None
        source_path = metadata.get("source_path", "inline")
        if source_path and source_path != "inline":
            _, ext = os.path.splitext(source_path)
            document_type = ext[1:] if ext else "txt"
        else:
            # Default to .py for code content
            document_type = "py"

        # Use proper filename with extension for LangExtract
        document_path = f"inline.{document_type}"

        # Convert semantic_context to string if it's a dict (LangExtract expects string)
        semantic_context_str = None
        if metadata:
            semantic_context = metadata.get("semantic_context")
            if semantic_context:
                if isinstance(semantic_context, dict):
                    # Convert dict to JSON string
                    semantic_context_str = json.dumps(semantic_context)
                else:
                    semantic_context_str = str(semantic_context)

        logger.info(
            f"🔍 [REL EXTRACT] Calling LangExtract | "
            f"endpoint={langextract_url}/extract/document | "
            f"entity_count={len(entity_list)} | document_type={document_type}"
        )

        try:
            payload = {
                "document_path": document_path,
                "content": content,
                "extraction_options": {
                    "include_semantic_analysis": True,
                },
                "update_knowledge_graph": False,
            }

            # Add semantic_context if available
            if semantic_context_str:
                payload["extraction_options"]["semantic_context"] = semantic_context_str

            response = await self.http_client.post(
                f"{langextract_url}/extract/document", json=payload, timeout=30.0
            )

            logger.info(
                f"🔍 [REL EXTRACT] LangExtract response | "
                f"status={response.status_code} | "
                f"content_type={response.headers.get('content-type')}"
            )

            if response.status_code == 200:
                data = response.json()
                relationships = data.get("relationships", [])

                # Success exit logging
                logger.info(
                    f"EXIT _extract_relationships_via_langextract: SUCCESS - "
                    f"relationships={len(relationships)}"
                )
                return relationships
            else:
                body_preview = (
                    response.text[:500]
                    if hasattr(response, "text")
                    else str(response.content)[:500]
                )
                logger.warning(
                    f"LangExtract failed | status={response.status_code} | "
                    f"body={body_preview}"
                )

                # Warning exit logging (not error since this is recoverable)
                logger.warning(
                    f"EXIT _extract_relationships_via_langextract: FAILED - "
                    f"status={response.status_code}, returning empty list"
                )
                return []

        except Exception as e:
            logger.error(
                f"EXIT _extract_relationships_via_langextract: ERROR - "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return []

    async def _enhance_entity_with_semantics(
        self, entity: KnowledgeEntity, content: str, metadata: Dict[str, Any]
    ) -> KnowledgeEntity:
        """Enhance entity with semantic analysis and embeddings"""

        # Generate embedding for entity with timeout wrapper
        entity_text = self._create_entity_text(entity, content)
        try:
            # Add timeout wrapper - configurable timeout per embedding (default 60s for vLLM)
            # Increased from 30s to 60s to handle queue delays during bulk operations
            timeout = float(os.getenv("EMBEDDING_GENERATION_TIMEOUT", "60.0"))
            embedding = await asyncio.wait_for(
                self._generate_embedding(entity_text), timeout=timeout
            )
            entity.embedding = embedding
        except asyncio.TimeoutError:
            logger.warning(
                f"⚠️ Embedding generation timeout for entity: {entity.name}, "
                f"continuing without embedding"
            )
            entity.embedding = []
        except Exception as e:
            logger.warning(
                f"⚠️ Embedding generation failed for entity: {entity.name}, "
                f"error: {e}, continuing without embedding"
            )
            entity.embedding = []

        # Update metadata with semantic analysis
        entity.metadata.extraction_method = "enhanced_semantic_extraction"
        entity.metadata.extraction_confidence = min(entity.confidence_score + 0.1, 1.0)

        # Add semantic properties
        semantic_props = await self._analyze_entity_semantics(entity, content)
        entity.properties.update(semantic_props)

        # Update confidence based on semantic analysis
        semantic_confidence = self._calculate_semantic_confidence(
            entity, semantic_props
        )
        entity.confidence_score = max(entity.confidence_score, semantic_confidence)

        return entity

    async def _enhance_code_entity(
        self,
        entity: KnowledgeEntity,
        content: str,
        language: str,
        metadata: Dict[str, Any],
    ) -> KnowledgeEntity:
        """Enhance code entity with advanced code analysis"""

        # Start with base semantic enhancement
        enhanced_entity = await self._enhance_entity_with_semantics(
            entity, content, metadata
        )

        # Add code-specific analysis
        if entity.entity_type in [EntityType.FUNCTION, EntityType.METHOD]:
            code_metrics = await self._analyze_function_complexity(entity, content)
            enhanced_entity.properties.update(code_metrics)

        elif entity.entity_type == EntityType.CLASS:
            class_metrics = await self._analyze_class_structure(entity, content)
            enhanced_entity.properties.update(class_metrics)

        # Detect patterns and code smells
        patterns = await self._detect_code_patterns(entity, content)
        if patterns:
            enhanced_entity.properties["detected_patterns"] = [
                {"pattern": p.pattern_name, "confidence": p.confidence}
                for p in patterns
            ]

        return enhanced_entity

    async def _extract_semantic_patterns(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract entities based on semantic patterns"""
        entities = []

        for pattern_category, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                matches = self._find_pattern_matches(pattern, content)
                for match in matches:
                    entity = KnowledgeEntity(
                        entity_id=self._generate_entity_id(
                            f"{pattern_category}_{match['text']}", source_path
                        ),
                        name=f"{pattern_category.replace('_', ' ').title()}: {match['text']}",
                        entity_type=EntityType.PATTERN,
                        description=f"Detected {pattern_category} pattern",
                        source_path=source_path,
                        confidence_score=match["confidence"],
                        source_line_number=match.get("line_number"),
                        properties={
                            "pattern_category": pattern_category,
                            "pattern_text": match["text"],
                        },
                    )

                    # Generate embedding for pattern
                    embedding = await self._generate_embedding(entity.description)
                    entity.embedding = embedding

                    entities.append(entity)

        return entities

    async def _extract_code_patterns(
        self, content: str, source_path: str, language: Optional[str]
    ) -> List[KnowledgeEntity]:
        """Extract code-specific patterns and structures"""
        entities = []

        # API endpoint detection
        if language in ["python", "javascript", "typescript"]:
            api_entities = await self._extract_api_endpoints(content, source_path)
            entities.extend(api_entities)

        # Database operation detection
        db_entities = await self._extract_database_operations(content, source_path)
        entities.extend(db_entities)

        # Configuration and constants
        config_entities = await self._extract_configuration_entities(
            content, source_path
        )
        entities.extend(config_entities)

        return entities

    async def _create_document_entity(
        self, content: str, source_path: str, metadata: Dict[str, Any]
    ) -> KnowledgeEntity:
        """Create comprehensive document entity"""

        from pathlib import Path

        doc_name = Path(source_path).stem
        doc_type = Path(source_path).suffix

        # Generate document summary embedding
        summary_text = content[:500] + "..." if len(content) > 500 else content
        embedding = await self._generate_embedding(summary_text)

        # Calculate document metrics
        word_count = len(content.split())
        line_count = len(content.split("\n"))
        char_count = len(content)

        entity = KnowledgeEntity(
            entity_id=self._generate_entity_id(f"document_{doc_name}", source_path),
            name=f"Document: {doc_name}",
            entity_type=EntityType.DOCUMENT,
            description=f"Document content from {Path(source_path).name}",
            source_path=source_path,
            confidence_score=0.95,
            embedding=embedding,
            properties={
                "document_type": doc_type,
                "word_count": word_count,
                "line_count": line_count,
                "character_count": char_count,
                "summary": summary_text,
                **metadata,
            },
        )

        return entity

    async def _analyze_entity_semantics(
        self, entity: KnowledgeEntity, content: str
    ) -> Dict[str, Any]:
        """Analyze entity semantics and context"""

        properties = {}

        # Context analysis
        entity_context = self._extract_entity_context(entity, content)
        if entity_context:
            properties["context"] = entity_context

        # Complexity estimation
        if entity.entity_type in [EntityType.FUNCTION, EntityType.METHOD]:
            complexity = self._estimate_complexity(entity, content)
            properties["estimated_complexity"] = complexity

        # Documentation detection
        docs = self._find_entity_documentation(entity, content)
        if docs:
            properties["documentation"] = docs
            properties["is_documented"] = True
        else:
            properties["is_documented"] = False

        return properties

    async def _analyze_function_complexity(
        self, entity: KnowledgeEntity, content: str
    ) -> Dict[str, Any]:
        """Analyze function complexity metrics"""

        metrics = {}

        # Extract function body
        func_body = self._extract_function_body(entity, content)
        if not func_body:
            return metrics

        # Count various complexity indicators
        metrics.update(
            {
                "lines_of_code": len(func_body.split("\n")),
                "cyclomatic_complexity": self._calculate_cyclomatic_complexity(
                    func_body
                ),
                "parameter_count": self._count_parameters(func_body),
                "return_statements": func_body.count("return"),
                "nested_levels": self._calculate_nesting_depth(func_body),
                "has_loops": any(keyword in func_body for keyword in ["for", "while"]),
                "has_conditionals": any(
                    keyword in func_body for keyword in ["if", "elif", "else"]
                ),
                "has_exceptions": any(
                    keyword in func_body for keyword in ["try", "except", "raise"]
                ),
            }
        )

        return metrics

    async def _analyze_class_structure(
        self, entity: KnowledgeEntity, content: str
    ) -> Dict[str, Any]:
        """Analyze class structure and characteristics"""

        metrics = {}

        # Extract class body
        class_body = self._extract_class_body(entity, content)
        if not class_body:
            return metrics

        # Count class characteristics
        methods = len([line for line in class_body.split("\n") if "def " in line])
        properties = len(
            [line for line in class_body.split("\n") if "@property" in line]
        )

        metrics.update(
            {
                "method_count": methods,
                "property_count": properties,
                "lines_of_code": len(class_body.split("\n")),
                "has_init": "__init__" in class_body,
                "has_str": "__str__" in class_body,
                "has_repr": "__repr__" in class_body,
                "inheritance_depth": self._calculate_inheritance_depth(class_body),
            }
        )

        return metrics

    async def _detect_code_patterns(
        self, entity: KnowledgeEntity, content: str
    ) -> List[PatternMatch]:
        """Detect code patterns and anti-patterns"""

        patterns = []
        entity_content = self._get_entity_content(entity, content)

        # Check for design patterns
        for pattern_name, pattern_regex in [
            ("Singleton", r"__new__.*cls.*instance"),
            ("Factory", r"def\s+create.*return.*\("),
            ("Observer", r"def\s+notify.*for.*in.*observers"),
            ("Decorator", r"def\s+\w+.*def\s+wrapper"),
        ]:
            if self._matches_pattern(pattern_regex, entity_content):
                patterns.append(
                    PatternMatch(
                        pattern_name=pattern_name,
                        pattern_type="design_pattern",
                        confidence=0.8,
                        description=f"Detected {pattern_name} design pattern",
                        location={"entity_id": entity.entity_id},
                    )
                )

        # Check for code smells
        for smell_name, smell_regex in [
            ("Long Parameter List", r"def\s+\w+\([^)]{80,}\)"),
            ("Deep Nesting", r"(\s{12,})if"),
            ("Magic Numbers", r"\b\d{2,}\b"),
        ]:
            if self._matches_pattern(smell_regex, entity_content):
                patterns.append(
                    PatternMatch(
                        pattern_name=smell_name,
                        pattern_type="code_smell",
                        confidence=0.7,
                        description=f"Detected {smell_name} code smell",
                        severity="medium",
                        recommendation=f"Consider refactoring to address {smell_name}",
                    )
                )

        return patterns

    async def _extract_api_endpoints(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract API endpoint entities"""
        entities = []

        # FastAPI/Flask endpoint patterns
        endpoint_patterns = [
            r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            r'app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
        ]

        for pattern in endpoint_patterns:
            matches = self._find_pattern_matches(pattern, content)
            for match in matches:
                method = (
                    match["groups"][0].upper()
                    if "groups" in match and match["groups"]
                    else "UNKNOWN"
                )
                path = (
                    match["groups"][1]
                    if "groups" in match and len(match["groups"]) > 1
                    else match["text"]
                )

                entity = KnowledgeEntity(
                    entity_id=self._generate_entity_id(
                        f"api_{method}_{path}", source_path
                    ),
                    name=f"{method} {path}",
                    entity_type=EntityType.API_ENDPOINT,
                    description=f"API endpoint: {method} {path}",
                    source_path=source_path,
                    confidence_score=0.9,
                    source_line_number=match.get("line_number"),
                    properties={
                        "http_method": method,
                        "endpoint_path": path,
                        "endpoint_type": "REST",
                    },
                )

                # Generate embedding
                embedding = await self._generate_embedding(
                    f"API endpoint {method} {path}"
                )
                entity.embedding = embedding

                entities.append(entity)

        return entities

    async def _extract_database_operations(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract database operation entities"""
        entities = []

        # SQL patterns
        sql_patterns = {
            "SELECT": r"SELECT\s+.*\s+FROM\s+(\w+)",
            "INSERT": r"INSERT\s+INTO\s+(\w+)",
            "UPDATE": r"UPDATE\s+(\w+)\s+SET",
            "DELETE": r"DELETE\s+FROM\s+(\w+)",
        }

        for operation, pattern in sql_patterns.items():
            matches = self._find_pattern_matches(pattern, content)
            for match in matches:
                table_name = (
                    match["groups"][0]
                    if "groups" in match and match["groups"]
                    else "unknown"
                )

                entity = KnowledgeEntity(
                    entity_id=self._generate_entity_id(
                        f"db_{operation}_{table_name}", source_path
                    ),
                    name=f"DB {operation}: {table_name}",
                    entity_type=EntityType.SERVICE,
                    description=f"Database {operation} operation on {table_name}",
                    source_path=source_path,
                    confidence_score=0.85,
                    source_line_number=match.get("line_number"),
                    properties={
                        "operation_type": operation,
                        "target_table": table_name,
                        "service_type": "database",
                    },
                )

                entities.append(entity)

        return entities

    async def _extract_configuration_entities(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract configuration and constant entities"""
        entities = []

        # Configuration patterns
        config_patterns = [
            r"(\w+_CONFIG)\s*=",
            r"(\w+_SETTINGS)\s*=",
            r'([A-Z_]{3,})\s*=\s*["\']',  # Constants
            r"config\.(\w+)",
            r"settings\.(\w+)",
        ]

        for pattern in config_patterns:
            matches = self._find_pattern_matches(pattern, content)
            for match in matches:
                config_name = (
                    match["groups"][0]
                    if "groups" in match and match["groups"]
                    else match["text"]
                )

                entity = KnowledgeEntity(
                    entity_id=self._generate_entity_id(
                        f"config_{config_name}", source_path
                    ),
                    name=config_name,
                    entity_type=EntityType.CONFIG_SETTING,
                    description=f"Configuration setting: {config_name}",
                    source_path=source_path,
                    confidence_score=0.8,
                    source_line_number=match.get("line_number"),
                    properties={"config_type": "application_setting"},
                )

                entities.append(entity)

        return entities

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI-compatible API (vLLM) with retry logic and rate limiting.

        Uses semaphore-based rate limiting to prevent queue buildup at vLLM service.
        During bulk operations, this maintains ~200ms latency instead of 15-30s queue waits.
        """
        # Entry logging (debug to avoid noise)
        logger.debug(
            f"ENTER _generate_embedding: text_length={len(text)}, "
            f"model={self.embedding_model}"
        )

        # Use rate limiter to prevent queue buildup
        async with self.rate_limiter:
            for attempt in range(2):  # 2 attempts max
                try:
                    # Use OpenAI-compatible API format (vLLM)
                    response = await self.http_client.post(
                        f"{self.embedding_model_url}/v1/embeddings",
                        json={"model": self.embedding_model, "input": text},
                    )

                    if response.status_code == 200:
                        result = response.json()
                        # OpenAI format: {"data": [{"embedding": [...]}]}
                        data = result.get("data", [])
                        if data and len(data) > 0:
                            embedding = data[0].get("embedding", [])
                            logger.debug(
                                f"EXIT _generate_embedding: SUCCESS - dimensions={len(embedding)}"
                            )
                            return embedding
                        else:
                            logger.warning(
                                f"No embedding data in response (attempt {attempt+1}/2)"
                            )
                            if attempt == 0:
                                await asyncio.sleep(0.5)  # Brief pause before retry
                            else:
                                logger.warning(
                                    f"EXIT _generate_embedding: FAILED - returning empty list"
                                )
                                return []
                    else:
                        logger.warning(
                            f"Failed to generate embedding (attempt {attempt+1}/2): "
                            f"{response.status_code}"
                        )
                        if attempt == 0:
                            await asyncio.sleep(0.5)  # Brief pause before retry
                        else:
                            logger.warning(
                                f"EXIT _generate_embedding: FAILED - returning empty list"
                            )
                            return []

                except Exception as e:
                    if attempt == 0:
                        logger.debug(
                            f"Embedding attempt {attempt+1}/2 failed, retrying: "
                            f"{type(e).__name__}: {e}"
                        )
                        await asyncio.sleep(0.5)  # Brief pause before retry
                    else:
                        logger.error(
                            f"EXIT _generate_embedding: ERROR - {type(e).__name__}: {str(e)}",
                            exc_info=True,
                        )
                        raise  # Raise on final attempt to be caught by timeout wrapper

            logger.warning("EXIT _generate_embedding: FAILED - returning empty list")
            return []

    async def _add_quality_scores(
        self, entities: List[KnowledgeEntity], content: str, source_path: str
    ):
        """Add quality scores to entities"""
        for entity in entities:
            quality_score = self.quality_scorer.score_entity(entity, content)

            entity.properties["quality_score"] = quality_score.overall_score
            entity.properties["quality_factors"] = quality_score.factors

            if quality_score.temporal_relevance:
                entity.properties["temporal_relevance"] = (
                    quality_score.temporal_relevance
                )

    def _create_entity_text(self, entity: KnowledgeEntity, content: str) -> str:
        """Create text representation of entity for embedding"""
        context = self._extract_entity_context(entity, content)
        return f"{entity.name}: {entity.description}. Context: {context}"

    def _extract_entity_context(self, entity: KnowledgeEntity, content: str) -> str:
        """Extract contextual information around entity"""
        if not entity.source_line_number:
            return ""

        lines = content.split("\n")
        start_line = max(0, entity.source_line_number - 3)
        end_line = min(len(lines), entity.source_line_number + 2)

        context_lines = lines[start_line:end_line]
        return " ".join(line.strip() for line in context_lines if line.strip())

    def _calculate_semantic_confidence(
        self, entity: KnowledgeEntity, semantic_props: Dict[str, Any]
    ) -> float:
        """Calculate confidence based on semantic analysis"""
        base_confidence = 0.6

        # Boost confidence for documented entities
        if semantic_props.get("is_documented"):
            base_confidence += 0.2

        # Boost confidence for entities with context
        if semantic_props.get("context"):
            base_confidence += 0.1

        # Adjust based on entity type
        type_confidence = {
            EntityType.FUNCTION: 0.9,
            EntityType.CLASS: 0.9,
            EntityType.METHOD: 0.85,
            EntityType.API_ENDPOINT: 0.95,
            EntityType.DOCUMENT: 0.8,
        }

        type_boost = type_confidence.get(entity.entity_type, 0.7)
        return min(base_confidence * type_boost, 1.0)

    # Helper methods for pattern matching and analysis

    def _find_pattern_matches(self, pattern: str, content: str) -> List[Dict[str, Any]]:
        """Find pattern matches with line numbers and context"""
        import re

        matches = []

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                matches.append(
                    {
                        "text": match.group(0),
                        "groups": match.groups(),
                        "line_number": line_num,
                        "confidence": 0.8,
                        "context": line.strip(),
                    }
                )

        return matches

    def _matches_pattern(self, pattern: str, content: str) -> bool:
        """Check if content matches pattern"""
        import re

        return bool(re.search(pattern, content, re.IGNORECASE | re.MULTILINE))

    def _get_entity_content(self, entity: KnowledgeEntity, full_content: str) -> str:
        """Extract content specific to entity"""
        if entity.source_line_number:
            lines = full_content.split("\n")
            start = max(0, entity.source_line_number - 1)

            # Try to find the end of the entity (simple heuristic)
            end = start + 20  # Default to 20 lines
            for i in range(start + 1, min(len(lines), start + 50)):
                if (
                    lines[i]
                    and not lines[i].startswith(" ")
                    and not lines[i].startswith("\t")
                ):
                    end = i
                    break

            return "\n".join(lines[start:end])

        return full_content

    def _extract_function_body(self, entity: KnowledgeEntity, content: str) -> str:
        """Extract function body content"""
        return self._get_entity_content(entity, content)

    def _extract_class_body(self, entity: KnowledgeEntity, content: str) -> str:
        """Extract class body content"""
        return self._get_entity_content(entity, content)

    def _calculate_cyclomatic_complexity(self, code: str) -> int:
        """Simple cyclomatic complexity calculation"""
        complexity_keywords = [
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "and",
            "or",
        ]
        return sum(code.count(keyword) for keyword in complexity_keywords) + 1

    def _count_parameters(self, code: str) -> int:
        """Count function parameters"""
        import re

        match = re.search(r"def\s+\w+\(([^)]*)\)", code)
        if match:
            params = match.group(1).split(",")
            return len([p.strip() for p in params if p.strip() and p.strip() != "self"])
        return 0

    def _calculate_nesting_depth(self, code: str) -> int:
        """Calculate maximum nesting depth"""
        max_depth = 0

        for line in code.split("\n"):
            stripped = line.lstrip()
            if stripped:
                indent_level = (
                    len(line) - len(stripped)
                ) // 4  # Assuming 4-space indentation
                max_depth = max(max_depth, indent_level)

        return max_depth

    def _calculate_inheritance_depth(self, code: str) -> int:
        """Calculate inheritance depth (simplified)"""
        import re

        match = re.search(r"class\s+\w+\(([^)]+)\)", code)
        if match:
            bases = match.group(1).split(",")
            return len(
                [b.strip() for b in bases if b.strip() and b.strip() != "object"]
            )
        return 0

    def _estimate_complexity(self, entity: KnowledgeEntity, content: str) -> str:
        """Estimate entity complexity level"""
        entity_content = self._get_entity_content(entity, content)
        lines = len(entity_content.split("\n"))

        if lines < 10:
            return "low"
        elif lines < 30:
            return "medium"
        elif lines < 100:
            return "high"
        else:
            return "very_high"

    def _find_entity_documentation(
        self, entity: KnowledgeEntity, content: str
    ) -> Optional[str]:
        """Find documentation for entity"""
        entity_content = self._get_entity_content(entity, content)

        # Look for docstrings
        import re

        docstring_patterns = [r'"""(.*?)"""', r"'''(.*?)'''", r"#\s*(.*?)$"]

        for pattern in docstring_patterns:
            matches = re.findall(pattern, entity_content, re.DOTALL | re.MULTILINE)
            if matches:
                return matches[0].strip()

        return None
