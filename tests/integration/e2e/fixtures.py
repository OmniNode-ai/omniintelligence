# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""E2E test fixtures for OMN-1800 pattern learning pipeline tests.

This module provides fixture functions that return test data for E2E integration
tests of the pattern learning pipeline. All fixtures use deterministic UUIDs for
test repeatability.

Fixture Categories:
    - TC1: Successful session data (tool usage with success outcome)
    - TC2: Failed session data (tool execution failures)
    - TC3: Duplicate session data (for deduplication testing)
    - TC4: Feedback data (session outcomes for metrics updates)

Usage:
    from tests.integration.e2e.fixtures import (
        sample_successful_session_data,
        sample_failed_session_data,
        sample_duplicate_session_data,
        sample_feedback_data,
    )

    def test_pattern_learning():
        training_data = sample_successful_session_data()
        # ... test with training_data
"""

from __future__ import annotations

from uuid import UUID

from omniintelligence.nodes.node_pattern_learning_compute.models import (
    TrainingDataItemDict,
)

# =============================================================================
# Deterministic Session UUIDs
# =============================================================================

# TC1: Successful sessions
SESSION_ID_SUCCESS_1 = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID_SUCCESS_2 = UUID("11111111-2222-2222-2222-222222222222")
SESSION_ID_SUCCESS_3 = UUID("11111111-3333-3333-3333-333333333333")

# TC2: Failed sessions
SESSION_ID_FAILED_1 = UUID("22222222-1111-1111-1111-111111111111")
SESSION_ID_FAILED_2 = UUID("22222222-2222-2222-2222-222222222222")

# TC3: Duplicate detection sessions
SESSION_ID_DUPLICATE_A = UUID("33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SESSION_ID_DUPLICATE_B = UUID("33333333-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# TC4: Feedback sessions
SESSION_ID_FEEDBACK_1 = UUID("44444444-1111-1111-1111-111111111111")
SESSION_ID_FEEDBACK_2 = UUID("44444444-2222-2222-2222-222222222222")

# Pattern IDs for feedback tests
PATTERN_ID_1 = UUID("aaaaaaaa-0001-0001-0001-000000000001")
PATTERN_ID_2 = UUID("aaaaaaaa-0002-0002-0002-000000000002")

# Correlation IDs
CORRELATION_ID_1 = UUID("cccccccc-1111-1111-1111-111111111111")
CORRELATION_ID_2 = UUID("cccccccc-2222-2222-2222-222222222222")


# =============================================================================
# TC1: Successful Session Data
# =============================================================================


def sample_successful_session_data() -> list[TrainingDataItemDict]:
    """Return training data items representing successful tool usage sessions.

    This fixture provides 5 training data items representing a successful
    coding session with multiple tool executions:
    - 3 prompts processed
    - 5 tool executions completed
    - Success outcome

    Returns:
        List of TrainingDataItemDict representing successful patterns.
    """
    return [
        # Item 1: Code generation pattern
        TrainingDataItemDict(
            item_id=f"success-{SESSION_ID_SUCCESS_1}-001",
            source_file="src/services/user_service.py",
            language="python",
            code_snippet='''async def create_user(
    self,
    email: str,
    name: str,
    role: str = "user",
) -> User:
    """Create a new user with validation.

    Args:
        email: User email address (must be unique).
        name: Display name for the user.
        role: User role, defaults to "user".

    Returns:
        Newly created User instance.

    Raises:
        ValidationError: If email format is invalid.
        DuplicateError: If email already exists.
    """
    if not self._validate_email(email):
        raise ValidationError("Invalid email format")

    existing = await self.repository.find_by_email(email)
    if existing:
        raise DuplicateError(f"Email {email} already registered")

    user = User(email=email, name=name, role=role)
    return await self.repository.save(user)''',
            pattern_type="code_generation",
            pattern_name="async_service_method",
            labels=["async", "validation", "repository_pattern", "error_handling"],
            confidence=0.92,
            context="User service implementation with async repository pattern",
            framework="fastapi",
        ),
        # Item 2: Refactoring pattern
        TrainingDataItemDict(
            item_id=f"success-{SESSION_ID_SUCCESS_2}-001",
            source_file="src/handlers/handler_payment.py",
            language="python",
            code_snippet='''def process_payment(
    amount: Decimal,
    currency: str,
    payment_method: PaymentMethod,
    *,
    idempotency_key: str,
) -> PaymentResult:
    """Process a payment with idempotency guarantee.

    Uses the idempotency key to ensure exactly-once processing
    even if the request is retried.
    """
    # Check for existing transaction
    existing = _lookup_by_idempotency_key(idempotency_key)
    if existing:
        return PaymentResult.from_transaction(existing)

    # Validate amount
    if amount <= Decimal("0"):
        return PaymentResult.error("Amount must be positive")

    # Execute payment
    transaction = _execute_payment(
        amount=amount,
        currency=currency,
        method=payment_method,
    )

    # Store with idempotency key
    _store_transaction(transaction, idempotency_key)

    return PaymentResult.success(transaction)''',
            pattern_type="refactoring",
            pattern_name="idempotent_operation",
            labels=["idempotency", "payment", "validation", "error_handling"],
            confidence=0.88,
            context="Payment handler refactored for idempotency",
            framework="pydantic",
        ),
        # Item 3: Test generation pattern
        TrainingDataItemDict(
            item_id=f"success-{SESSION_ID_SUCCESS_2}-002",
            source_file="tests/unit/test_user_service.py",
            language="python",
            code_snippet='''@pytest.mark.asyncio
async def test_create_user_success(
    user_service: UserService,
    mock_repository: AsyncMock,
) -> None:
    """Test successful user creation with valid input."""
    # Arrange
    mock_repository.find_by_email.return_value = None
    mock_repository.save.return_value = User(
        id=uuid4(),
        email="test@example.com",
        name="Test User",
        role="user",
    )

    # Act
    result = await user_service.create_user(
        email="test@example.com",
        name="Test User",
    )

    # Assert
    assert result.email == "test@example.com"
    assert result.name == "Test User"
    mock_repository.find_by_email.assert_called_once_with("test@example.com")
    mock_repository.save.assert_called_once()''',
            pattern_type="code_generation",
            pattern_name="pytest_async_test",
            labels=["pytest", "async", "mocking", "unit_test"],
            confidence=0.95,
            context="Unit test for async service method",
            framework="pytest",
        ),
        # Item 4: API endpoint pattern
        TrainingDataItemDict(
            item_id=f"success-{SESSION_ID_SUCCESS_3}-001",
            source_file="src/api/routes/users.py",
            language="python",
            code_snippet='''@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
    },
)
async def create_user(
    request: CreateUserRequest,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Create a new user account.

    Args:
        request: User creation request with email and name.
        user_service: Injected user service dependency.

    Returns:
        Created user data.
    """
    try:
        user = await user_service.create_user(
            email=request.email,
            name=request.name,
        )
        return UserResponse.from_user(user)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )''',
            pattern_type="code_generation",
            pattern_name="fastapi_endpoint",
            labels=["fastapi", "rest_api", "dependency_injection", "error_handling"],
            confidence=0.91,
            context="FastAPI endpoint with proper error handling",
            framework="fastapi",
        ),
        # Item 5: Configuration pattern
        TrainingDataItemDict(
            item_id=f"success-{SESSION_ID_SUCCESS_3}-002",
            source_file="src/config/settings.py",
            language="python",
            code_snippet='''class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables
    with the APP_ prefix (e.g., APP_DATABASE_URL).
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Connection pool size",
    )

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)

    # Security
    secret_key: SecretStr = Field(
        ...,
        min_length=32,
        description="Secret key for JWT signing",
    )''',
            pattern_type="code_generation",
            pattern_name="pydantic_settings",
            labels=["pydantic", "configuration", "settings", "environment"],
            confidence=0.94,
            context="Application settings with Pydantic BaseSettings",
            framework="pydantic",
        ),
    ]


# =============================================================================
# TC2: Failed Session Data
# =============================================================================


def sample_failed_session_data() -> list[TrainingDataItemDict]:
    """Return training data items representing failed tool execution sessions.

    This fixture provides training data items that demonstrate common
    failure patterns during tool execution:
    - File not found errors
    - Syntax errors in generated code
    - Validation failures

    Returns:
        List of TrainingDataItemDict representing failure patterns.
    """
    return [
        # Item 1: Code with syntax error
        TrainingDataItemDict(
            item_id=f"failed-{SESSION_ID_FAILED_1}-001",
            source_file="src/broken/incomplete_handler.py",
            language="python",
            code_snippet='''def handle_request(request: Request) -> Response:
    """Handle incoming request.

    NOTE: This code has an intentional syntax error for testing.
    """
    data = request.json()
    if data.get("action") == "create":
        result = create_item(data
        # Missing closing parenthesis - incomplete code
    return Response(status=200''',
            pattern_type="debugging",
            pattern_name="syntax_error_incomplete",
            labels=["error", "syntax", "incomplete", "debugging"],
            confidence=0.35,
            context="Incomplete code with syntax error - tool execution failed",
            framework="unknown",
        ),
        # Item 2: Import error pattern
        TrainingDataItemDict(
            item_id=f"failed-{SESSION_ID_FAILED_1}-002",
            source_file="src/broken/missing_imports.py",
            language="python",
            code_snippet='''# Missing import statements
class DataProcessor:
    """Process data using pandas and numpy.

    NOTE: Imports are missing - will fail at runtime.
    """

    def process(self, data: DataFrame) -> ndarray:
        # Uses pandas.DataFrame and numpy.ndarray without imports
        df = DataFrame(data)  # NameError: DataFrame not defined
        return df.values.astype(float64)  # NameError: float64 not defined''',
            pattern_type="debugging",
            pattern_name="missing_imports",
            labels=["error", "import", "runtime", "debugging"],
            confidence=0.28,
            context="Code with missing imports - execution would fail",
            framework="pandas",
        ),
        # Item 3: Type error pattern
        TrainingDataItemDict(
            item_id=f"failed-{SESSION_ID_FAILED_2}-001",
            source_file="src/broken/type_mismatch.py",
            language="python",
            code_snippet='''from typing import List

def calculate_average(numbers: List[int]) -> float:
    """Calculate average of numbers.

    NOTE: This will fail with TypeError when called incorrectly.
    """
    # Bug: sum() of strings instead of integers
    total = sum(numbers)  # Works with int list
    count = len(numbers)
    return total / count

# Incorrect usage that causes failure
result = calculate_average(["1", "2", "3"])  # TypeError: unsupported operand type''',
            pattern_type="debugging",
            pattern_name="type_mismatch",
            labels=["error", "type", "runtime", "debugging"],
            confidence=0.42,
            context="Type mismatch causing runtime TypeError",
            framework="typing",
        ),
        # Item 4: File operation error
        TrainingDataItemDict(
            item_id=f"failed-{SESSION_ID_FAILED_2}-002",
            source_file="src/broken/file_error.py",
            language="python",
            code_snippet='''from pathlib import Path

def read_config(config_path: str) -> dict:
    """Read configuration from file.

    NOTE: No error handling for missing files.
    """
    path = Path(config_path)
    # Bug: No existence check before reading
    content = path.read_text()  # FileNotFoundError if path doesn't exist
    return json.loads(content)  # Also missing json import

# Call with non-existent file
config = read_config("/nonexistent/config.json")''',
            pattern_type="debugging",
            pattern_name="file_not_found",
            labels=["error", "file", "io", "debugging"],
            confidence=0.38,
            context="Missing file existence check causes FileNotFoundError",
            framework="pathlib",
        ),
    ]


# =============================================================================
# TC3: Duplicate Session Data
# =============================================================================


def sample_duplicate_session_data() -> tuple[
    list[TrainingDataItemDict], list[TrainingDataItemDict]
]:
    """Return two lists of training data for deduplication testing.

    This fixture provides two sets of training data that contain semantically
    similar patterns. The pattern learning pipeline should detect these as
    duplicates and deduplicate them appropriately.

    Returns:
        Tuple of (session_a_data, session_b_data) where both contain
        similar patterns that should be deduplicated.
    """
    # Session A: Original patterns
    session_a = [
        TrainingDataItemDict(
            item_id=f"dup-a-{SESSION_ID_DUPLICATE_A}-001",
            source_file="src/services/order_service.py",
            language="python",
            code_snippet='''async def create_order(
    self,
    user_id: UUID,
    items: list[OrderItem],
) -> Order:
    """Create a new order for a user.

    Args:
        user_id: The ID of the user placing the order.
        items: List of items to include in the order.

    Returns:
        Created Order instance.
    """
    # Validate user exists
    user = await self.user_repo.get(user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")

    # Calculate total
    total = sum(item.price * item.quantity for item in items)

    # Create order
    order = Order(
        user_id=user_id,
        items=items,
        total=total,
        status=OrderStatus.PENDING,
    )
    return await self.order_repo.save(order)''',
            pattern_type="code_generation",
            pattern_name="async_service_create",
            labels=["async", "service", "repository", "validation"],
            confidence=0.90,
            context="Order service with user validation",
            framework="fastapi",
        ),
        TrainingDataItemDict(
            item_id=f"dup-a-{SESSION_ID_DUPLICATE_A}-002",
            source_file="src/api/routes/orders.py",
            language="python",
            code_snippet='''@router.post("/orders", response_model=OrderResponse)
async def create_order(
    request: CreateOrderRequest,
    order_service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    """Create a new order for the authenticated user."""
    order = await order_service.create_order(
        user_id=current_user.id,
        items=request.items,
    )
    return OrderResponse.from_order(order)''',
            pattern_type="code_generation",
            pattern_name="fastapi_post_endpoint",
            labels=["fastapi", "endpoint", "dependency_injection"],
            confidence=0.88,
            context="Order creation endpoint",
            framework="fastapi",
        ),
    ]

    # Session B: Similar patterns (should be detected as duplicates)
    session_b = [
        # Similar to session_a[0] - same pattern, different entity
        TrainingDataItemDict(
            item_id=f"dup-b-{SESSION_ID_DUPLICATE_B}-001",
            source_file="src/services/invoice_service.py",
            language="python",
            code_snippet='''async def create_invoice(
    self,
    customer_id: UUID,
    line_items: list[LineItem],
) -> Invoice:
    """Create a new invoice for a customer.

    Args:
        customer_id: The ID of the customer.
        line_items: List of line items for the invoice.

    Returns:
        Created Invoice instance.
    """
    # Validate customer exists
    customer = await self.customer_repo.get(customer_id)
    if not customer:
        raise NotFoundError(f"Customer {customer_id} not found")

    # Calculate total
    total = sum(item.amount * item.quantity for item in line_items)

    # Create invoice
    invoice = Invoice(
        customer_id=customer_id,
        line_items=line_items,
        total=total,
        status=InvoiceStatus.DRAFT,
    )
    return await self.invoice_repo.save(invoice)''',
            pattern_type="code_generation",
            pattern_name="async_service_create",
            labels=["async", "service", "repository", "validation"],
            confidence=0.91,
            context="Invoice service with customer validation",
            framework="fastapi",
        ),
        # Similar to session_a[1] - same pattern, different entity
        TrainingDataItemDict(
            item_id=f"dup-b-{SESSION_ID_DUPLICATE_B}-002",
            source_file="src/api/routes/invoices.py",
            language="python",
            code_snippet='''@router.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(
    request: CreateInvoiceRequest,
    invoice_service: InvoiceService = Depends(get_invoice_service),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    """Create a new invoice for the authenticated user's customer."""
    invoice = await invoice_service.create_invoice(
        customer_id=request.customer_id,
        line_items=request.line_items,
    )
    return InvoiceResponse.from_invoice(invoice)''',
            pattern_type="code_generation",
            pattern_name="fastapi_post_endpoint",
            labels=["fastapi", "endpoint", "dependency_injection"],
            confidence=0.87,
            context="Invoice creation endpoint",
            framework="fastapi",
        ),
    ]

    return session_a, session_b


# =============================================================================
# TC4: Feedback Data
# =============================================================================


def sample_feedback_data() -> list[
    dict[
        str,
        UUID | str | list[UUID],
    ]
]:
    """Return session outcome data for feedback/metrics update testing.

    This fixture provides session outcome data that should be used to update
    pattern metrics (success_count, failure_count, etc.) based on whether
    the session that used those patterns succeeded or failed.

    The data structure matches what would be processed by NodePatternFeedbackEffect
    for updating learned_patterns metrics.

    Returns:
        List of feedback data dictionaries containing:
        - session_id: UUID of the session
        - outcome: "success" or "failed"
        - pattern_ids: List of pattern UUIDs used in the session
        - correlation_id: Optional correlation ID for tracing
    """
    return [
        # Feedback 1: Successful session with two patterns
        {
            "session_id": SESSION_ID_FEEDBACK_1,
            "outcome": "success",
            "pattern_ids": [PATTERN_ID_1, PATTERN_ID_2],
            "correlation_id": CORRELATION_ID_1,
        },
        # Feedback 2: Failed session with one pattern
        {
            "session_id": SESSION_ID_FEEDBACK_2,
            "outcome": "failed",
            "pattern_ids": [PATTERN_ID_1],
            "correlation_id": CORRELATION_ID_2,
        },
    ]


def sample_session_outcomes() -> list[dict[str, UUID | str | dict[str, str] | None]]:
    """Return ClaudeSessionOutcome-compatible data for feedback testing.

    This fixture provides data in the format expected by the pattern feedback
    effect node, matching the ClaudeSessionOutcome (ModelClaudeCodeSessionOutcome)
    schema from omnibase_core.

    Returns:
        List of session outcome dictionaries compatible with ClaudeSessionOutcome.
    """
    return [
        # Outcome 1: Successful session
        {
            "session_id": SESSION_ID_FEEDBACK_1,
            "outcome": "success",
            "error": None,
            "correlation_id": CORRELATION_ID_1,
        },
        # Outcome 2: Failed session with error details
        {
            "session_id": SESSION_ID_FEEDBACK_2,
            "outcome": "failed",
            "error": {
                "error_code": "TOOL_EXECUTION_FAILED",
                "error_type": "runtime",
                "error_message": "Edit tool failed: file not found",
                "component": "Edit",
                "operation": "write_file",
            },
            "correlation_id": CORRELATION_ID_2,
        },
    ]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "CORRELATION_ID_1",
    "CORRELATION_ID_2",
    "PATTERN_ID_1",
    "PATTERN_ID_2",
    "SESSION_ID_DUPLICATE_A",
    "SESSION_ID_DUPLICATE_B",
    "SESSION_ID_FAILED_1",
    "SESSION_ID_FAILED_2",
    "SESSION_ID_FEEDBACK_1",
    "SESSION_ID_FEEDBACK_2",
    "SESSION_ID_SUCCESS_1",
    "SESSION_ID_SUCCESS_2",
    "SESSION_ID_SUCCESS_3",
    # Fixture functions
    "sample_duplicate_session_data",
    "sample_failed_session_data",
    "sample_feedback_data",
    "sample_session_outcomes",
    "sample_successful_session_data",
]
