# test_framework_performance_real.py - Real Environment Performance Testing
import statistics
import time

from framework_cache import (
    FrameworkCache,
    FrameworkError,
    establish_archon_testing_context,
)


def test_framework_performance():
    """Run comprehensive framework performance tests in real environment."""
    print("🧪 Testing Specialist - Framework Performance Validation")
    print("=" * 60)

    # Clear any existing cache instances for clean testing
    FrameworkCache._instance = None
    FrameworkCache._load_times = {}

    try:
        # Test 1: Framework Cache Performance
        print("\n1️⃣ Framework Cache Performance Test")
        cache = FrameworkCache()

        # First access (cache miss)
        print("   Testing initial load (cache miss)...")
        start = time.perf_counter_ns()
        requirements = cache.load_core_requirements()
        first_access_ms = (time.perf_counter_ns() - start) / 1_000_000

        print(f"   ✅ Core requirements loaded: {len(requirements)} top-level keys")
        print(f"   ⏱️ First access: {first_access_ms:.3f}ms")

        # Test cached access performance (multiple samples)
        print("   Testing cached access performance...")
        access_times = []
        for i in range(10):
            start = time.perf_counter_ns()
            cache.load_core_requirements()
            cached_access_ms = (time.perf_counter_ns() - start) / 1_000_000
            access_times.append(cached_access_ms)

        avg_cached = statistics.mean(access_times)
        max_cached = max(access_times)
        min_cached = min(access_times)

        print("   📊 Cached access statistics (10 samples):")
        print(f"      Average: {avg_cached:.6f}ms")
        print(f"      Maximum: {max_cached:.6f}ms")
        print(f"      Minimum: {min_cached:.6f}ms")
        print("      Target: <0.5ms")

        cache_target_met = avg_cached < 0.5
        print(
            f"   {'✅' if cache_target_met else '❌'} Cache performance target: {'MET' if cache_target_met else 'NOT MET'}"
        )

        # Test 2: Template Discovery Performance
        print("\n2️⃣ Template Discovery Performance Test")
        start = time.perf_counter_ns()
        templates = cache.load_templates_spec()
        template_discovery_ms = (time.perf_counter_ns() - start) / 1_000_000

        template_count = len(templates.get("templates", {}))
        print(f"   ✅ Templates discovered: {template_count}")
        print(f"   ⏱️ Discovery time: {template_discovery_ms:.3f}ms")

        template_target_met = template_discovery_ms < 100
        print(
            f"   {'✅' if template_target_met else '❌'} Template discovery target (<100ms): {'MET' if template_target_met else 'NOT MET'}"
        )

        # Test 3: Agent Initialization Performance
        print("\n3️⃣ Agent Initialization Performance Test")
        initialization_times = []

        for i in range(5):
            # Reset cache for each test
            FrameworkCache._instance = None
            FrameworkCache._load_times = {}

            start = time.perf_counter_ns()
            result = establish_archon_testing_context()
            init_time_ms = (time.perf_counter_ns() - start) / 1_000_000
            initialization_times.append(init_time_ms)

            print(f"   Run {i+1}: {init_time_ms:.3f}ms - {'✅' if result else '❌'}")

        avg_init = statistics.mean(initialization_times)
        max_init = max(initialization_times)
        min_init = min(initialization_times)

        print("   📊 Initialization statistics (5 runs):")
        print(f"      Average: {avg_init:.3f}ms")
        print(f"      Maximum: {max_init:.3f}ms")
        print(f"      Minimum: {min_init:.3f}ms")
        print("      Target: <300ms")

        init_target_met = avg_init < 300
        print(
            f"   {'✅' if init_target_met else '❌'} Initialization target: {'MET' if init_target_met else 'NOT MET'}"
        )

        # Test 4: Performance Metrics Validation
        print("\n4️⃣ Performance Metrics Validation")
        final_cache = FrameworkCache()
        final_cache.load_core_requirements()
        final_cache.load_templates_spec()

        metrics = final_cache.get_performance_metrics()
        print("   📋 Cache configuration:")
        print(f"      Base path: {metrics['base_path']}")
        print(f"      Templates dir: {metrics['templates_dir']}")
        print(f"      Cache hits: {metrics['cache_hits']}")
        print(f"      Target met: {metrics['target_met']}")
        print(f"      Average access: {metrics['average_access_ms']:.6f}ms")

        # Test 5: Stress Test (Regression Protection)
        print("\n5️⃣ Stress Test - Regression Protection")
        stress_times = []

        for i in range(50):
            start = time.perf_counter_ns()
            final_cache.load_core_requirements()
            final_cache.load_templates_spec()
            stress_time_ms = (time.perf_counter_ns() - start) / 1_000_000
            stress_times.append(stress_time_ms)

        stress_avg = statistics.mean(stress_times)
        stress_max = max(stress_times)

        print("   📈 Stress test results (50 operations):")
        print(f"      Average: {stress_avg:.6f}ms")
        print(f"      Maximum: {stress_max:.6f}ms")

        stress_target_met = stress_avg < 0.5
        print(
            f"   {'✅' if stress_target_met else '❌'} Stress test target: {'MET' if stress_target_met else 'NOT MET'}"
        )

        # Final Assessment
        print("\n" + "=" * 60)
        print("🎯 FINAL ASSESSMENT")
        print("=" * 60)

        all_targets_met = all(
            [cache_target_met, template_target_met, init_target_met, stress_target_met]
        )

        print(
            f"Overall Status: {'✅ ALL TARGETS MET' if all_targets_met else '⚠️ SOME TARGETS NOT MET'}"
        )
        print("\nDetailed Results:")
        print(
            f"  Cache Performance (<0.5ms): {'✅ PASS' if cache_target_met else '❌ FAIL'} - {avg_cached:.6f}ms avg"
        )
        print(
            f"  Template Discovery (<100ms): {'✅ PASS' if template_target_met else '❌ FAIL'} - {template_discovery_ms:.3f}ms"
        )
        print(
            f"  Agent Initialization (<300ms): {'✅ PASS' if init_target_met else '❌ FAIL'} - {avg_init:.3f}ms avg"
        )
        print(
            f"  Stress Test Stability (<0.5ms): {'✅ PASS' if stress_target_met else '❌ FAIL'} - {stress_avg:.6f}ms avg"
        )

        return {
            "cache_performance": {
                "target_met": cache_target_met,
                "first_access_ms": first_access_ms,
                "avg_cached_ms": avg_cached,
                "max_cached_ms": max_cached,
            },
            "template_discovery": {
                "target_met": template_target_met,
                "discovery_time_ms": template_discovery_ms,
                "template_count": template_count,
            },
            "agent_initialization": {
                "target_met": init_target_met,
                "avg_init_ms": avg_init,
                "max_init_ms": max_init,
            },
            "stress_test": {
                "target_met": stress_target_met,
                "avg_stress_ms": stress_avg,
                "operations_count": 50,
            },
            "overall_success": all_targets_met,
        }

    except FrameworkError as e:
        print(f"❌ Framework Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    results = test_framework_performance()
    if results:
        print(f"\n🏁 Test completed. Overall success: {results['overall_success']}")
    else:
        print("\n💥 Test failed with errors.")
