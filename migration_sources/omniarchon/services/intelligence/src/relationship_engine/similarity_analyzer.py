"""
Similarity Analyzer Module
===========================

Analyzes semantic similarity between patterns using:
1. AST structural similarity
2. Qdrant vector similarity (if patterns are vectorized)
3. Code metrics similarity

Combines multiple similarity signals to provide comprehensive similarity scoring.
"""

import ast
from typing import Dict, List, Optional, Tuple

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class SimilarityAnalyzer:
    """
    Analyzes semantic similarity between code patterns.

    Uses multiple similarity signals:
    1. Structural similarity (AST-based)
    2. Vector similarity (Qdrant-based, if available)
    3. Metrics similarity (complexity, maintainability)

    Combines these signals with configurable weights.
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "code_patterns",
        use_qdrant: bool = True,
    ):
        """
        Initialize similarity analyzer.

        Args:
            qdrant_host: Qdrant host address
            qdrant_port: Qdrant port
            collection_name: Qdrant collection name for patterns
            use_qdrant: Whether to use Qdrant for vector similarity
        """
        self.use_qdrant = use_qdrant and QDRANT_AVAILABLE
        self.collection_name = collection_name

        if self.use_qdrant:
            try:
                self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
            except Exception as e:
                print(f"Warning: Failed to connect to Qdrant: {e}")
                self.use_qdrant = False

    def calculate_similarity(
        self,
        pattern_a: Dict,
        pattern_b: Dict,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate comprehensive similarity between two patterns.

        Args:
            pattern_a: First pattern dictionary with keys:
                - implementation: Source code
                - complexity: Cyclomatic complexity (optional)
                - maintainability_index: MI score (optional)
                - pattern_id: UUID (optional, for Qdrant lookup)
            pattern_b: Second pattern dictionary (same structure)
            weights: Custom weights for similarity components (optional)
                Default: {"structural": 0.5, "vector": 0.3, "metrics": 0.2}

        Returns:
            Tuple of (overall_similarity, component_scores)
                - overall_similarity: Weighted average (0.0-1.0)
                - component_scores: Dict with individual scores
        """
        # Default weights
        if weights is None:
            weights = {
                "structural": 0.5,
                "vector": 0.3 if self.use_qdrant else 0.0,
                "metrics": 0.2 if self.use_qdrant else 0.5,
            }

        component_scores = {}

        # 1. Structural similarity (AST-based)
        structural_score = self._calculate_structural_similarity(
            pattern_a["implementation"], pattern_b["implementation"]
        )
        component_scores["structural"] = structural_score

        # 2. Vector similarity (Qdrant-based)
        if self.use_qdrant and "pattern_id" in pattern_a and "pattern_id" in pattern_b:
            vector_score = self._calculate_vector_similarity(
                pattern_a["pattern_id"], pattern_b["pattern_id"]
            )
            component_scores["vector"] = vector_score
        else:
            component_scores["vector"] = 0.0

        # 3. Metrics similarity
        metrics_score = self._calculate_metrics_similarity(pattern_a, pattern_b)
        component_scores["metrics"] = metrics_score

        # Calculate weighted average
        total_score = sum(
            component_scores[key] * weights.get(key, 0.0) for key in component_scores
        )

        # Normalize by actual weights used
        total_weight = sum(
            weights.get(key, 0.0)
            for key in component_scores
            if component_scores[key] > 0.0
        )

        if total_weight > 0:
            overall_similarity = total_score / total_weight
        else:
            overall_similarity = 0.0

        return round(overall_similarity, 4), component_scores

    def find_similar_patterns(
        self,
        pattern: Dict,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        """
        Find patterns similar to the given pattern using Qdrant.

        Args:
            pattern: Pattern dictionary with:
                - pattern_id: UUID for Qdrant lookup
                - implementation: Source code (fallback if no vector)
            top_k: Number of similar patterns to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of (pattern_id, similarity_score, component_scores) tuples
        """
        if not self.use_qdrant:
            return []

        # Query Qdrant for similar patterns
        try:
            # Get pattern vector from Qdrant
            pattern_id = pattern.get("pattern_id")
            if not pattern_id:
                return []

            # Search for similar patterns
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=pattern_id,  # Assuming pattern_id maps to vector
                limit=top_k + 1,  # +1 to exclude self
            )

            similar_patterns = []
            for result in search_results:
                if result.id == pattern_id:
                    continue  # Skip self

                similarity = result.score
                if similarity >= min_similarity:
                    similar_patterns.append(
                        (
                            result.id,
                            similarity,
                            {"vector": similarity, "structural": 0.0, "metrics": 0.0},
                        )
                    )

            return similar_patterns[:top_k]

        except Exception as e:
            print(f"Warning: Qdrant search failed: {e}")
            return []

    def _calculate_structural_similarity(
        self, source_code_a: str, source_code_b: str
    ) -> float:
        """
        Calculate structural similarity using AST.

        Similarity factors:
        - Number of functions (weight: 0.3)
        - Number of classes (weight: 0.3)
        - Similar function signatures (weight: 0.2)
        - Similar imports (weight: 0.2)

        Args:
            source_code_a: First pattern source code
            source_code_b: Second pattern source code

        Returns:
            Similarity score (0.0-1.0)
        """
        try:
            tree_a = ast.parse(source_code_a)
            tree_b = ast.parse(source_code_b)
        except SyntaxError:
            return 0.0

        features_a = self._extract_structural_features(tree_a)
        features_b = self._extract_structural_features(tree_b)

        scores = []

        # 1. Function count similarity
        func_count_a = features_a["function_count"]
        func_count_b = features_b["function_count"]
        if func_count_a == 0 and func_count_b == 0:
            func_similarity = 1.0
        else:
            func_similarity = 1.0 - abs(func_count_a - func_count_b) / max(
                func_count_a, func_count_b, 1
            )
        scores.append((func_similarity, 0.3))

        # 2. Class count similarity
        class_count_a = features_a["class_count"]
        class_count_b = features_b["class_count"]
        if class_count_a == 0 and class_count_b == 0:
            class_similarity = 1.0
        else:
            class_similarity = 1.0 - abs(class_count_a - class_count_b) / max(
                class_count_a, class_count_b, 1
            )
        scores.append((class_similarity, 0.3))

        # 3. Function signature similarity
        sig_overlap = len(
            features_a["function_signatures"] & features_b["function_signatures"]
        )
        sig_total = len(
            features_a["function_signatures"] | features_b["function_signatures"]
        )
        sig_similarity = sig_overlap / sig_total if sig_total > 0 else 0.0
        scores.append((sig_similarity, 0.2))

        # 4. Import similarity
        import_overlap = len(features_a["imports"] & features_b["imports"])
        import_total = len(features_a["imports"] | features_b["imports"])
        import_similarity = import_overlap / import_total if import_total > 0 else 0.0
        scores.append((import_similarity, 0.2))

        # Calculate weighted average
        total_score = sum(score * weight for score, weight in scores)

        return round(total_score, 4)

    def _calculate_vector_similarity(
        self, pattern_id_a: str, pattern_id_b: str
    ) -> float:
        """
        Calculate vector similarity using Qdrant.

        Args:
            pattern_id_a: First pattern UUID
            pattern_id_b: Second pattern UUID

        Returns:
            Cosine similarity score (0.0-1.0)
        """
        if not self.use_qdrant:
            return 0.0

        try:
            # Get vectors for both patterns
            # Note: This is a simplified implementation
            # In practice, you'd retrieve vectors and compute cosine similarity
            # For now, return placeholder
            return 0.0
        except Exception:
            return 0.0

    def _calculate_metrics_similarity(self, pattern_a: Dict, pattern_b: Dict) -> float:
        """
        Calculate similarity based on code metrics.

        Compares:
        - Cyclomatic complexity
        - Maintainability index

        Args:
            pattern_a: First pattern dictionary
            pattern_b: Second pattern dictionary

        Returns:
            Metrics similarity score (0.0-1.0)
        """
        scores = []

        # Complexity similarity
        complexity_a = pattern_a.get("complexity", 0)
        complexity_b = pattern_b.get("complexity", 0)

        if complexity_a == 0 and complexity_b == 0:
            complexity_similarity = 1.0
        else:
            # Normalize by max complexity (assume max 50)
            max_complexity = 50
            complexity_diff = abs(complexity_a - complexity_b)
            complexity_similarity = 1.0 - (complexity_diff / max_complexity)
            complexity_similarity = max(0.0, complexity_similarity)

        scores.append((complexity_similarity, 0.5))

        # Maintainability similarity
        maintainability_a = pattern_a.get("maintainability_index", 0.0)
        maintainability_b = pattern_b.get("maintainability_index", 0.0)

        if maintainability_a > 0 and maintainability_b > 0:
            # Both scores are 0-100 range
            maintainability_diff = abs(maintainability_a - maintainability_b)
            maintainability_similarity = 1.0 - (maintainability_diff / 100.0)
            maintainability_similarity = max(0.0, maintainability_similarity)
        else:
            maintainability_similarity = 0.0

        scores.append((maintainability_similarity, 0.5))

        # Calculate weighted average
        total_score = sum(score * weight for score, weight in scores)

        return round(total_score, 4)

    def _extract_structural_features(self, tree: ast.AST) -> Dict:
        """
        Extract structural features from AST.

        Args:
            tree: AST tree

        Returns:
            Dictionary with features
        """
        features = {
            "function_count": 0,
            "class_count": 0,
            "function_signatures": set(),
            "imports": set(),
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                features["function_count"] += 1
                signature = self._get_function_signature(node)
                features["function_signatures"].add(signature)

            elif isinstance(node, ast.ClassDef):
                features["class_count"] += 1

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    features["imports"].add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    features["imports"].add(node.module)

        return features

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Get function signature as string."""
        args = [arg.arg for arg in node.args.args]
        return f"{node.name}({', '.join(args)})"


# Example usage
if __name__ == "__main__":
    analyzer = SimilarityAnalyzer(use_qdrant=False)

    # Example patterns
    pattern_a = {
        "implementation": "def foo(x, y): return x + y",
        "complexity": 1,
        "maintainability_index": 75.0,
    }

    pattern_b = {
        "implementation": "def bar(a, b): return a + b",
        "complexity": 1,
        "maintainability_index": 72.0,
    }

    similarity, components = analyzer.calculate_similarity(pattern_a, pattern_b)

    print(f"Overall similarity: {similarity}")
    print("Component scores:")
    for key, score in components.items():
        print(f"  {key}: {score}")
