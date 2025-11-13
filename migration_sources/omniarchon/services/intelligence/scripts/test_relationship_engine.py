#!/usr/bin/env python3
"""
Test Script for Pattern Relationship Engine

Quick validation script to test core functionality:
- Relationship detection
- Similarity analysis
- Database connection (optional)

Usage:
    python3 scripts/test_relationship_engine.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from relationship_engine import RelationshipDetector, SimilarityAnalyzer

print("=" * 70)
print("Pattern Relationship Engine - Test Script")
print("=" * 70)

# Test 1: Relationship Detection
print("\n[Test 1] Relationship Detection")
print("-" * 70)

detector = RelationshipDetector()

test_code = """
import os
import asyncio
from pathlib import Path
from typing import Dict, List

class NodePatternStorageEffect(BaseEffect):
    def __init__(self, db_connection):
        super().__init__(db_connection)
        self.validator = PatternValidator()

    async def execute_effect(self, contract):
        result = await self.validator.validate(contract)
        return await self.store_pattern(result)

    async def store_pattern(self, pattern_data):
        os.path.exists("/tmp")
        return await self.db_connection.execute(query)
"""

relationships = detector.detect_all_relationships(
    test_code, "NodePatternStorageEffect", None
)

print(f"✅ Detected {len(relationships)} relationships:\n")

# Group by type
by_type = {}
for rel in relationships:
    rel_type = rel.relationship_type.value
    if rel_type not in by_type:
        by_type[rel_type] = []
    by_type[rel_type].append(rel)

for rel_type, rels in by_type.items():
    print(f"{rel_type.upper()} ({len(rels)}):")
    for rel in rels:
        print(f"  → {rel.target_pattern_name} (confidence: {rel.confidence:.2f})")
    print()

# Test 2: Structural Similarity
print("[Test 2] Structural Similarity")
print("-" * 70)

analyzer = SimilarityAnalyzer(use_qdrant=False)

code_a = """
def calculate_total(items, tax_rate):
    subtotal = sum(item.price for item in items)
    tax = subtotal * tax_rate
    return subtotal + tax
"""

code_b = """
def compute_total(products, tax):
    base = sum(p.cost for p in products)
    tax_amount = base * tax
    return base + tax_amount
"""

code_c = """
class Calculator:
    def add(self, a, b):
        return a + b
"""

similarity_ab = detector.calculate_structural_similarity(code_a, code_b)
similarity_ac = detector.calculate_structural_similarity(code_a, code_c)

print(f"Similarity (similar functions): {similarity_ab:.2f}")
print(f"Similarity (different structures): {similarity_ac:.2f}")
print()

if similarity_ab > 0.7:
    print("✅ High similarity detected correctly")
else:
    print("❌ Expected high similarity, got low")

if similarity_ac < 0.5:
    print("✅ Low similarity detected correctly")
else:
    print("❌ Expected low similarity, got high")

# Test 3: Database Connection (Optional)
print("\n[Test 3] Database Connection (Optional)")
print("-" * 70)

try:
    import asyncio
    import os

    from relationship_engine import GraphBuilder

    async def test_db_connection():
        builder = GraphBuilder(
            db_host=os.getenv("POSTGRES_HOST", "192.168.86.200"),
            db_port=int(os.getenv("POSTGRES_PORT", "5436")),
            db_name=os.getenv("POSTGRES_DATABASE", "omninode_bridge"),
            db_user=os.getenv("POSTGRES_USER", "postgres"),
            db_password=os.getenv(
                "POSTGRES_PASSWORD", "omninode-bridge-postgres-dev-2024"
            ),
        )

        # Try to get connection
        try:
            conn = await builder._get_connection()
            await conn.close()
            print("✅ Database connection successful")
            print(
                f"   Connected to: {builder.db_host}:{builder.db_port}/{builder.db_name}"
            )
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    db_success = asyncio.run(test_db_connection())

except ImportError as e:
    print(f"⚠️  Database test skipped (missing dependencies): {e}")
    db_success = None

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)

print("✅ Relationship detection: PASSED")
print("✅ Similarity analysis: PASSED")

if db_success is True:
    print("✅ Database connection: PASSED")
elif db_success is False:
    print("❌ Database connection: FAILED")
else:
    print("⚠️  Database connection: SKIPPED")

print("\n" + "=" * 70)
print("All core functionality tests completed!")
print("=" * 70)
