"""
Unit Tests for HTTP Retry Logic

Tests the retry_async, @with_retry decorator, and RetryableHTTPClient
implementations for correctness, performance, and thread safety.
"""

import asyncio
import time
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from infrastructure.http_retry import (
    NON_RETRYABLE_STATUS_CODES,
    RETRYABLE_STATUS_CODES,
    RetryableHTTPClient,
    RetryExhaustedError,
    get_retry_metrics,
    reset_retry_metrics,
    retry_async,
    should_retry_exception,
    should_retry_status_code,
    with_retry,
)


@pytest.fixture(autouse=True)
def reset_metrics_before_each_test():
    """Reset retry metrics before each test"""
    reset_retry_metrics()
    yield
    reset_retry_metrics()


class TestStatusCodeRetry:
    """Test status code retry logic"""

    def test_retryable_status_codes(self):
        """Verify retryable status codes are identified correctly"""
        for code in [408, 429, 500, 502, 503, 504]:
            assert should_retry_status_code(code), f"Status {code} should be retryable"

    def test_non_retryable_status_codes(self):
        """Verify non-retryable status codes (4xx) are identified correctly"""
        for code in [400, 401, 403, 404, 405, 422]:
            assert not should_retry_status_code(
                code
            ), f"Status {code} should NOT be retryable"

    def test_success_status_codes_not_retried(self):
        """Verify 2xx success codes are not retried"""
        for code in [200, 201, 204]:
            assert not should_retry_status_code(
                code
            ), f"Status {code} should NOT be retryable"


class TestExceptionRetry:
    """Test exception retry logic"""

    def test_retryable_exceptions(self):
        """Verify retryable exceptions are identified correctly"""
        retryable = [
            httpx.TimeoutException("timeout"),
            httpx.NetworkError("network"),
            httpx.ConnectError("connect"),
            httpx.ReadTimeout("read timeout"),
            httpx.WriteTimeout("write timeout"),
            ConnectionError("connection error"),
            ConnectionRefusedError("refused"),
            ConnectionResetError("reset"),
        ]
        for exc in retryable:
            assert should_retry_exception(
                exc
            ), f"{type(exc).__name__} should be retryable"

    def test_non_retryable_exceptions(self):
        """Verify non-retryable exceptions are identified correctly"""
        non_retryable = [
            ValueError("invalid value"),
            KeyError("missing key"),
            TypeError("wrong type"),
            RuntimeError("runtime error"),
        ]
        for exc in non_retryable:
            assert not should_retry_exception(
                exc
            ), f"{type(exc).__name__} should NOT be retryable"


class TestRetryAsync:
    """Test retry_async wrapper function"""

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self):
        """Test successful request completes without retries"""
        mock_func = AsyncMock(return_value="success")

        result = await retry_async(
            mock_func,
            max_attempts=3,
            backoff_delays=[1.0, 2.0, 4.0],
        )

        assert result == "success"
        assert mock_func.call_count == 1

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1
        assert metrics["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_transient_failure_with_recovery(self):
        """Test request succeeds after transient failures"""
        # Fail twice, then succeed
        mock_func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )

        start_time = time.time()
        result = await retry_async(
            mock_func,
            max_attempts=3,
            backoff_delays=[0.1, 0.2, 0.4],  # Shorter delays for testing
        )
        elapsed = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 3

        # Verify delays were applied (0.1s + 0.2s = ~0.3s)
        assert elapsed >= 0.3, f"Expected delay >= 0.3s, got {elapsed}s"

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1
        assert metrics["total_retries"] == 2
        assert "TimeoutException" in metrics["retries_by_reason"]

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test RetryExhaustedError raised when max retries exceeded"""
        # Always fail
        mock_func = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_async(
                mock_func,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            )

        assert exc_info.value.attempts == 3
        assert mock_func.call_count == 3

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["failed_attempts"] == 1
        assert metrics["total_retries"] == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_no_retry(self):
        """Test non-retryable exceptions fail immediately"""
        mock_func = AsyncMock(side_effect=ValueError("bad value"))

        with pytest.raises(ValueError):
            await retry_async(
                mock_func,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            )

        # Should fail on first attempt, no retries
        assert mock_func.call_count == 1

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["failed_attempts"] == 1
        assert metrics["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_http_response_with_retryable_status(self):
        """Test HTTP response with retryable status code triggers retry"""
        # Create mock responses
        response_503 = Mock(spec=httpx.Response)
        response_503.status_code = 503

        response_200 = Mock(spec=httpx.Response)
        response_200.status_code = 200

        mock_func = AsyncMock(side_effect=[response_503, response_200])

        result = await retry_async(
            mock_func,
            max_attempts=3,
            backoff_delays=[0.1, 0.2, 0.4],
        )

        assert result.status_code == 200
        assert mock_func.call_count == 2

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["total_retries"] == 1

    @pytest.mark.asyncio
    async def test_http_response_with_non_retryable_status(self):
        """Test HTTP response with 4xx status does not retry"""
        # Create mock response with 404
        response_404 = Mock(spec=httpx.Response)
        response_404.status_code = 404

        mock_func = AsyncMock(return_value=response_404)

        result = await retry_async(
            mock_func,
            max_attempts=3,
            backoff_delays=[0.1, 0.2, 0.4],
        )

        # Should return immediately without retry
        assert result.status_code == 404
        assert mock_func.call_count == 1

        # Verify no retries
        metrics = await get_retry_metrics()
        assert metrics["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test exponential backoff delays are applied correctly"""
        mock_func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )

        backoff_delays = [0.1, 0.2, 0.4]
        start_time = time.time()

        result = await retry_async(
            mock_func,
            max_attempts=4,
            backoff_delays=backoff_delays,
        )

        elapsed = time.time() - start_time

        assert result == "success"

        # Total delay should be sum of backoff delays
        expected_delay = sum(backoff_delays)
        assert (
            elapsed >= expected_delay
        ), f"Expected delay >= {expected_delay}s, got {elapsed}s"

        # Verify delays were recorded in metrics
        metrics = await get_retry_metrics()
        assert metrics["total_delay_seconds"] >= expected_delay


class TestWithRetryDecorator:
    """Test @with_retry decorator"""

    @pytest.mark.asyncio
    async def test_decorator_on_successful_function(self):
        """Test decorator on function that succeeds immediately"""

        @with_retry(max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])
        async def fetch_data():
            return "data"

        result = await fetch_data()
        assert result == "data"

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_decorator_with_arguments(self):
        """Test decorator on function with arguments"""

        @with_retry(max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])
        async def add_numbers(a: int, b: int) -> int:
            return a + b

        result = await add_numbers(5, 3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_decorator_with_retry(self):
        """Test decorator retries on failure"""
        attempt_count = {"count": 0}

        @with_retry(max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])
        async def flaky_function():
            attempt_count["count"] += 1
            if attempt_count["count"] < 3:
                raise httpx.TimeoutException("timeout")
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert attempt_count["count"] == 3

        # Verify metrics
        metrics = await get_retry_metrics()
        assert metrics["total_retries"] == 2

    @pytest.mark.asyncio
    async def test_decorator_with_custom_operation_name(self):
        """Test decorator with custom operation name for logging"""

        @with_retry(
            max_attempts=2,
            backoff_delays=[0.1],
            operation_name="Fetch User Data",
        )
        async def fetch_user(user_id: str):
            if user_id == "fail":
                raise httpx.TimeoutException("timeout")
            return f"User {user_id}"

        # Successful call
        result = await fetch_user("123")
        assert result == "User 123"

        # Failed call
        with pytest.raises(RetryExhaustedError):
            await fetch_user("fail")


class TestRetryableHTTPClient:
    """Test RetryableHTTPClient wrapper"""

    @pytest.mark.asyncio
    async def test_client_get_success(self):
        """Test GET request succeeds without retry"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with RetryableHTTPClient(
                timeout=10.0,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            ) as client:
                response = await client.get("https://api.example.com/data")

            assert response.status_code == 200
            assert mock_instance.get.call_count == 1

    @pytest.mark.asyncio
    async def test_client_post_with_retry(self):
        """Test POST request retries on failure"""
        with patch("httpx.AsyncClient") as mock_client_class:
            # First call fails with timeout, second succeeds
            mock_response_success = Mock(spec=httpx.Response)
            mock_response_success.status_code = 201

            mock_instance = AsyncMock()
            mock_instance.post.side_effect = [
                httpx.TimeoutException("timeout"),
                mock_response_success,
            ]
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with RetryableHTTPClient(
                timeout=10.0,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            ) as client:
                response = await client.post(
                    "https://api.example.com/create",
                    json={"key": "value"},
                )

            assert response.status_code == 201
            assert mock_instance.post.call_count == 2

    @pytest.mark.asyncio
    async def test_client_all_http_methods(self):
        """Test all HTTP methods have retry support"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            mock_instance = AsyncMock()
            for method in ["get", "post", "put", "delete", "patch"]:
                setattr(mock_instance, method, AsyncMock(return_value=mock_response))
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with RetryableHTTPClient(
                timeout=10.0,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            ) as client:
                # Test each HTTP method
                await client.get("https://api.example.com/data")
                await client.post("https://api.example.com/create", json={})
                await client.put("https://api.example.com/update/1", json={})
                await client.delete("https://api.example.com/delete/1")
                await client.patch("https://api.example.com/patch/1", json={})

            # Verify all methods were called
            assert mock_instance.get.call_count == 1
            assert mock_instance.post.call_count == 1
            assert mock_instance.put.call_count == 1
            assert mock_instance.delete.call_count == 1
            assert mock_instance.patch.call_count == 1

    @pytest.mark.asyncio
    async def test_client_context_manager_cleanup(self):
        """Test client properly closes on context manager exit"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with RetryableHTTPClient() as client:
                pass  # Just test cleanup

            # Verify client was closed
            mock_instance.aclose.assert_called_once()


class TestMetrics:
    """Test retry metrics tracking"""

    @pytest.mark.asyncio
    async def test_metrics_tracking_success(self):
        """Test metrics are tracked correctly for successful operations"""
        mock_func = AsyncMock(return_value="success")

        await retry_async(mock_func, max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])

        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1
        assert metrics["failed_attempts"] == 0
        assert metrics["total_retries"] == 0
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_metrics_tracking_with_retries(self):
        """Test metrics track retries correctly"""
        mock_func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )

        await retry_async(mock_func, max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])

        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1
        assert metrics["total_retries"] == 2
        assert "TimeoutException" in metrics["retries_by_reason"]

    @pytest.mark.asyncio
    async def test_metrics_tracking_failure(self):
        """Test metrics track failures correctly"""
        mock_func = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(RetryExhaustedError):
            await retry_async(mock_func, max_attempts=3, backoff_delays=[0.1, 0.2, 0.4])

        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 0
        assert metrics["failed_attempts"] == 1
        assert metrics["total_retries"] == 3
        assert metrics["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_metrics_reset(self):
        """Test metrics can be reset"""
        mock_func = AsyncMock(return_value="success")
        await retry_async(mock_func)

        # Verify metrics were recorded
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 1

        # Reset
        reset_retry_metrics()

        # Verify metrics are cleared
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 0
        assert metrics["successful_attempts"] == 0
        assert metrics["total_retries"] == 0


class TestConcurrency:
    """Test thread safety and concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_retries(self):
        """Test multiple concurrent retry operations"""

        async def flaky_operation(operation_id: int):
            if operation_id % 2 == 0:
                # Even IDs succeed immediately
                return f"success-{operation_id}"
            else:
                # Odd IDs fail once then succeed
                if not hasattr(flaky_operation, f"attempt_{operation_id}"):
                    setattr(flaky_operation, f"attempt_{operation_id}", 1)
                    raise httpx.TimeoutException("timeout")
                return f"success-{operation_id}"

        # Run 10 concurrent operations
        tasks = [
            retry_async(
                flaky_operation,
                operation_id,
                max_attempts=3,
                backoff_delays=[0.1, 0.2, 0.4],
            )
            for operation_id in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all operations completed successfully
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result == f"success-{i}"

        # Verify metrics tracked all operations
        metrics = await get_retry_metrics()
        assert metrics["total_attempts"] == 10
        assert metrics["successful_attempts"] == 10


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        """Test behavior with max_attempts=1 (no retries)"""
        mock_func = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_async(mock_func, max_attempts=1, backoff_delays=[])

        assert exc_info.value.attempts == 1
        assert mock_func.call_count == 1

        metrics = await get_retry_metrics()
        assert metrics["total_retries"] == 1  # Attempted 1 retry after initial failure

    @pytest.mark.asyncio
    async def test_backoff_delays_shorter_than_attempts(self):
        """Test when backoff_delays list is shorter than max_attempts"""
        mock_func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )

        # Only 2 delays for 4 attempts - last delay should be reused
        result = await retry_async(
            mock_func,
            max_attempts=4,
            backoff_delays=[0.1, 0.2],
        )

        assert result == "success"
        assert mock_func.call_count == 4

    @pytest.mark.asyncio
    async def test_empty_backoff_delays(self):
        """Test with empty backoff delays (immediate retry)"""
        mock_func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )

        start_time = time.time()
        result = await retry_async(
            mock_func,
            max_attempts=2,
            backoff_delays=[],
        )
        elapsed = time.time() - start_time

        assert result == "success"
        # Should complete quickly with no delays
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_http_status_error_with_retry(self):
        """Test httpx.HTTPStatusError is handled correctly"""
        mock_response_503 = Mock(spec=httpx.Response)
        mock_response_503.status_code = 503

        mock_response_200 = Mock(spec=httpx.Response)
        mock_response_200.status_code = 200

        exc_503 = httpx.HTTPStatusError(
            "Service Unavailable",
            request=Mock(),
            response=mock_response_503,
        )

        mock_func = AsyncMock(side_effect=[exc_503, mock_response_200])

        result = await retry_async(
            mock_func,
            max_attempts=3,
            backoff_delays=[0.1, 0.2, 0.4],
        )

        assert result.status_code == 200
        assert mock_func.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
