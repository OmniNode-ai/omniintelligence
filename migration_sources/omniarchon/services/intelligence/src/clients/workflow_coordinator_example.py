"""
Workflow Coordinator Client - Usage Examples

Demonstrates how to use the WorkflowCoordinatorClient for various workflow orchestration scenarios.
"""

import asyncio
import os
import sys
from uuid import uuid4

# Add config path for centralized timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from src.config.timeout_config import get_async_timeout, get_http_timeout
from workflow_coordinator_client import WorkflowCoordinatorClient
from workflow_coordinator_exceptions import (
    WorkflowCoordinatorTimeoutError,
    WorkflowNotFoundError,
)
from workflow_coordinator_models import (
    CoordinationStrategy,
    WorkflowNode,
)


# NOTE: correlation_id support enabled for tracing
async def example_1_simple_workflow():
    """
    Example 1: Trigger and poll a simple sequential workflow.
    """
    print("\n=== Example 1: Simple Sequential Workflow ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Define workflow nodes
        nodes = [
            WorkflowNode(
                node_name="data_validator",
                node_type="COMPUTE",
                priority=100,
                timeout_seconds=get_async_timeout("standard"),
                parameters={"strict_mode": True},
            ),
            WorkflowNode(
                node_name="data_transformer",
                node_type="COMPUTE",
                priority=90,
                timeout_seconds=get_async_timeout("long"),
                parameters={"format": "json"},
            ),
            WorkflowNode(
                node_name="data_writer",
                node_type="EFFECT",
                priority=80,
                timeout_seconds=get_async_timeout("standard"),
                parameters={"destination": "s3://bucket/output"},
            ),
        ]

        # Trigger workflow
        print("Triggering workflow...")
        response = await client.trigger_workflow(
            workflow_name="data_processing_pipeline",
            workflow_nodes=nodes,
            coordination_strategy=CoordinationStrategy.SEQUENTIAL,
            workflow_parameters={"batch_size": 1000},
            metadata={"project_id": "proj-123", "environment": "production"},
        )

        print(f"Workflow triggered: {response.workflow_id}")
        print(f"Initial status: {response.status}")

        # Poll for completion
        print("\nPolling for completion...")
        final_status = await client.poll_workflow_completion(
            workflow_id=response.workflow_id,
            timeout_seconds=get_async_timeout("long"),
            poll_interval_seconds=get_async_timeout("quick"),
        )

        print("\nWorkflow completed!")
        print(f"Final status: {final_status.status}")
        print(f"Duration: {final_status.duration_seconds:.2f}s")
        print(
            f"Nodes completed: {final_status.completed_nodes}/{final_status.total_nodes}"
        )


async def example_2_parallel_workflow_with_dependencies():
    """
    Example 2: Parallel workflow with node dependencies (DAG).
    """
    print("\n=== Example 2: Parallel Workflow with Dependencies ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Create node IDs for dependencies
        validator_a_id = uuid4()
        validator_b_id = uuid4()
        processor_id = uuid4()

        # Define DAG workflow
        nodes = [
            # Phase 1: Parallel validators
            WorkflowNode(
                node_id=validator_a_id,
                node_name="validator_a",
                node_type="COMPUTE",
                priority=100,
                timeout_seconds=get_async_timeout("standard"),
            ),
            WorkflowNode(
                node_id=validator_b_id,
                node_name="validator_b",
                node_type="COMPUTE",
                priority=100,
                timeout_seconds=get_async_timeout("standard"),
            ),
            # Phase 2: Processor (depends on both validators)
            WorkflowNode(
                node_id=processor_id,
                node_name="processor",
                node_type="EFFECT",
                dependencies=[validator_a_id, validator_b_id],
                priority=90,
                timeout_seconds=get_async_timeout("long"),
            ),
        ]

        # Trigger workflow
        print("Triggering DAG workflow...")
        response = await client.trigger_workflow(
            workflow_name="parallel_validation_pipeline",
            workflow_nodes=nodes,
            coordination_strategy=CoordinationStrategy.DAG,
            enable_checkpointing=True,
        )

        print(f"Workflow triggered: {response.workflow_id}")

        # Monitor progress with status checks
        workflow_id = response.workflow_id
        while True:
            status = await client.get_workflow_status(workflow_id)

            print(
                f"\rProgress: {status.progress_percentage:.1f}% - {status.status}",
                end="",
            )

            if status.status in ["COMPLETED", "FAILED", "CANCELLED"]:
                print(f"\n\nWorkflow finished: {status.status}")
                break

            await asyncio.sleep(3)


async def example_3_workflow_cancellation():
    """
    Example 3: Cancel a running workflow.
    """
    print("\n=== Example 3: Workflow Cancellation ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Trigger a long-running workflow (1 hour)
        nodes = [
            WorkflowNode(
                node_name="long_process",
                node_type="COMPUTE",
                timeout_seconds=3600,  # Intentionally high for demo
            )
        ]

        print("Triggering long-running workflow...")
        response = await client.trigger_workflow(
            workflow_name="long_running_pipeline", workflow_nodes=nodes
        )

        workflow_id = response.workflow_id
        print(f"Workflow started: {workflow_id}")

        # Wait a bit
        await asyncio.sleep(2)

        # Cancel it
        print("\nCancelling workflow...")
        cancel_response = await client.cancel_workflow(workflow_id)

        print("Workflow cancelled!")
        print(f"Previous status: {cancel_response.previous_status}")
        print(f"Cancelled at: {cancel_response.cancelled_at}")


async def example_4_list_active_workflows():
    """
    Example 4: List all active workflows.
    """
    print("\n=== Example 4: List Active Workflows ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Get active workflows
        print("Fetching active workflows...")
        response = await client.list_active_workflows()

        print(f"\nTotal active workflows: {response.total_count}")

        if response.workflows:
            print("\nActive workflows:")
            for workflow in response.workflows:
                print(f"\n  ID: {workflow.workflow_id}")
                print(f"  Name: {workflow.workflow_name}")
                print(f"  Status: {workflow.status}")
                print(f"  Progress: {workflow.progress_percentage:.1f}%")
                print(f"  Created: {workflow.created_at}")
        else:
            print("\nNo active workflows found.")


async def example_5_error_handling():
    """
    Example 5: Comprehensive error handling.
    """
    print("\n=== Example 5: Error Handling ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Example 5a: Workflow not found
        print("Example 5a: Handling workflow not found...")
        try:
            fake_id = uuid4()
            await client.get_workflow_status(fake_id)
        except WorkflowNotFoundError as e:
            print(f"✓ Caught WorkflowNotFoundError: {e.workflow_id}")

        # Example 5b: Timeout handling
        print("\nExample 5b: Handling timeout...")
        try:
            nodes = [WorkflowNode(node_name="test", node_type="COMPUTE")]
            response = await client.trigger_workflow(
                workflow_name="test_workflow", workflow_nodes=nodes
            )

            # Poll with very short timeout (intentionally short for demo)
            await client.poll_workflow_completion(
                workflow_id=response.workflow_id,
                timeout_seconds=1,  # Intentionally short to trigger timeout
                poll_interval_seconds=0.5,  # Fast polling for demo
            )
        except WorkflowCoordinatorTimeoutError as e:
            print(f"✓ Caught timeout after {e.timeout_seconds}s")

        # Example 5c: Service unavailable with retry
        print("\nExample 5c: Service handles retries automatically...")
        print("(Circuit breaker and retry logic work transparently)")


async def example_6_metrics_monitoring():
    """
    Example 6: Monitor client metrics.
    """
    print("\n=== Example 6: Metrics Monitoring ===\n")

    async with WorkflowCoordinatorClient() as client:
        # Trigger some workflows
        for i in range(3):
            nodes = [
                WorkflowNode(
                    node_name=f"task_{i}",
                    node_type="COMPUTE",
                    timeout_seconds=get_http_timeout("default"),
                )
            ]
            await client.trigger_workflow(
                workflow_name=f"test_workflow_{i}", workflow_nodes=nodes
            )

        # Get metrics
        metrics = client.get_metrics()

        print("Client Metrics:")
        print(f"  Total requests: {metrics['total_requests']}")
        print(f"  Successful requests: {metrics['successful_requests']}")
        print(f"  Failed requests: {metrics['failed_requests']}")
        print(f"  Success rate: {metrics['success_rate']:.2%}")
        print(f"  Avg duration: {metrics['avg_duration_ms']:.2f}ms")
        print(f"  Workflows triggered: {metrics['workflows_triggered']}")
        print(f"  Circuit breaker state: {metrics['circuit_breaker_state']}")
        print(f"  Service healthy: {metrics['is_healthy']}")


async def example_7_health_check():
    """
    Example 7: Check service health.
    """
    print("\n=== Example 7: Health Check ===\n")

    async with WorkflowCoordinatorClient() as client:
        health = await client.check_health()

        print("Service Health:")
        print(f"  Healthy: {health.get('healthy')}")
        print(f"  Response time: {health.get('response_time_ms', 'N/A')}ms")
        print(f"  Last check: {health.get('last_check')}")

        if not health.get("healthy"):
            print(f"  Error: {health.get('error')}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Workflow Coordinator Client - Usage Examples")
    print("=" * 60)

    examples = [
        ("Simple Sequential Workflow", example_1_simple_workflow),
        (
            "Parallel Workflow with Dependencies",
            example_2_parallel_workflow_with_dependencies,
        ),
        ("Workflow Cancellation", example_3_workflow_cancellation),
        ("List Active Workflows", example_4_list_active_workflows),
        ("Error Handling", example_5_error_handling),
        ("Metrics Monitoring", example_6_metrics_monitoring),
        ("Health Check", example_7_health_check),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nRunning all examples...\n")

    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            import traceback

            traceback.print_exc()

        await asyncio.sleep(1)  # Brief pause between examples

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
