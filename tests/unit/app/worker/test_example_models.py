"""Unit tests for worker package Pydantic models.

Tests model validation, serialization, and business logic without
requiring Temporal or any external dependencies.
"""

import pytest
from pydantic import ValidationError

from src.app.worker.activities.example import PaymentInput, PaymentOutput
from src.app.worker.workflows.example import OrderInput, OrderOutput


class TestPaymentInput:
    """Test PaymentInput model validation."""

    def test_valid_payment_input(self):
        """Test creating a valid PaymentInput."""
        payment = PaymentInput(order_id="ORD-123", amount=99.99)

        assert payment.order_id == "ORD-123"
        assert payment.amount == 99.99

    def test_payment_input_with_zero_amount(self):
        """Test PaymentInput allows zero amount."""
        payment = PaymentInput(order_id="ORD-123", amount=0.0)

        assert payment.amount == 0.0

    def test_payment_input_with_negative_amount(self):
        """Test PaymentInput allows negative amounts (refunds)."""
        payment = PaymentInput(order_id="ORD-123", amount=-50.0)

        assert payment.amount == -50.0

    def test_payment_input_serialization(self):
        """Test PaymentInput serializes correctly."""
        payment = PaymentInput(order_id="ORD-123", amount=99.99)
        data = payment.model_dump()

        assert data == {"order_id": "ORD-123", "amount": 99.99}

    def test_payment_input_from_dict(self):
        """Test PaymentInput can be created from dictionary."""
        data = {"order_id": "ORD-456", "amount": 150.50}
        payment = PaymentInput(**data)

        assert payment.order_id == "ORD-456"
        assert payment.amount == 150.50


class TestPaymentOutput:
    """Test PaymentOutput model validation."""

    def test_valid_payment_output(self):
        """Test creating a valid PaymentOutput."""
        output = PaymentOutput(transaction_id="txn_abc123", status="completed")

        assert output.transaction_id == "txn_abc123"
        assert output.status == "completed"

    def test_payment_output_various_statuses(self):
        """Test PaymentOutput accepts various status values."""
        statuses = ["completed", "pending", "failed", "refunded"]

        for status in statuses:
            output = PaymentOutput(transaction_id="txn_123", status=status)
            assert output.status == status

    def test_payment_output_serialization(self):
        """Test PaymentOutput serializes correctly."""
        output = PaymentOutput(transaction_id="txn_xyz789", status="completed")
        data = output.model_dump()

        assert data == {"transaction_id": "txn_xyz789", "status": "completed"}


class TestOrderInput:
    """Test OrderInput model validation."""

    def test_valid_order_input(self):
        """Test creating a valid OrderInput."""
        order = OrderInput(
            order_id="ORD-001",
            customer_email="customer@example.com",
            amount=199.99,
            items=[{"sku": "WIDGET-1", "quantity": 2}],
        )

        assert order.order_id == "ORD-001"
        assert order.customer_email == "customer@example.com"
        assert order.amount == 199.99
        assert len(order.items) == 1

    def test_order_input_with_multiple_items(self):
        """Test OrderInput with multiple items."""
        order = OrderInput(
            order_id="ORD-002",
            customer_email="customer@example.com",
            amount=299.99,
            items=[
                {"sku": "WIDGET-1", "quantity": 2},
                {"sku": "GADGET-2", "quantity": 1},
                {"sku": "TOOL-3", "quantity": 3},
            ],
        )

        assert len(order.items) == 3
        assert order.items[0]["sku"] == "WIDGET-1"
        assert order.items[1]["sku"] == "GADGET-2"
        assert order.items[2]["sku"] == "TOOL-3"

    def test_order_input_with_empty_items(self):
        """Test OrderInput allows empty items list."""
        order = OrderInput(
            order_id="ORD-003",
            customer_email="customer@example.com",
            amount=0.0,
            items=[],
        )

        assert order.items == []

    def test_order_input_invalid_email(self):
        """Test OrderInput rejects invalid email addresses."""
        with pytest.raises(ValidationError) as exc_info:
            OrderInput(
                order_id="ORD-004",
                customer_email="not-an-email",
                amount=99.99,
                items=[],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("customer_email",) for error in errors)

    def test_order_input_email_validation(self):
        """Test OrderInput validates email addresses."""
        # Valid emails should work
        order = OrderInput(
            order_id="ORD-007",
            customer_email="Customer@Example.COM",
            amount=99.99,
            items=[],
        )

        # Email is stored (case may or may not be normalized depending on Pydantic version)
        assert "@" in order.customer_email
        assert "example.com" in order.customer_email.lower()

    def test_order_input_serialization(self):
        """Test OrderInput serializes correctly."""
        order = OrderInput(
            order_id="ORD-008",
            customer_email="test@example.com",
            amount=149.99,
            items=[{"sku": "ABC-123", "quantity": 1}],
        )
        data = order.model_dump()

        assert data["order_id"] == "ORD-008"
        assert data["customer_email"] == "test@example.com"
        assert data["amount"] == 149.99
        assert data["items"] == [{"sku": "ABC-123", "quantity": 1}]


class TestOrderOutput:
    """Test OrderOutput model validation."""

    def test_valid_order_output(self):
        """Test creating a valid OrderOutput."""
        output = OrderOutput(
            order_id="ORD-009",
            status="completed",
            total_amount=299.99,
            message="Order processed successfully",
        )

        assert output.order_id == "ORD-009"
        assert output.status == "completed"
        assert output.total_amount == 299.99
        assert output.message == "Order processed successfully"

    def test_order_output_various_statuses(self):
        """Test OrderOutput accepts various status values."""
        statuses = [
            "completed",
            "cancelled",
            "failed",
            "processing",
            "cancelled_after_payment",
        ]

        for status in statuses:
            output = OrderOutput(
                order_id="ORD-010",
                status=status,
                total_amount=100.0,
                message=f"Status: {status}",
            )
            assert output.status == status

    def test_order_output_with_zero_amount(self):
        """Test OrderOutput allows zero total amount."""
        output = OrderOutput(
            order_id="ORD-011",
            status="cancelled",
            total_amount=0.0,
            message="Order cancelled before payment",
        )

        assert output.total_amount == 0.0

    def test_order_output_serialization(self):
        """Test OrderOutput serializes correctly."""
        output = OrderOutput(
            order_id="ORD-015",
            status="completed",
            total_amount=499.99,
            message="Successfully processed order",
        )
        data = output.model_dump()

        assert data == {
            "order_id": "ORD-015",
            "status": "completed",
            "total_amount": 499.99,
            "message": "Successfully processed order",
        }

    def test_order_output_long_message(self):
        """Test OrderOutput handles long messages."""
        long_message = "A" * 1000
        output = OrderOutput(
            order_id="ORD-016", status="failed", total_amount=0.0, message=long_message
        )

        assert len(output.message) == 1000
        assert output.message == long_message


class TestModelInteroperability:
    """Test models work together correctly."""

    def test_order_input_to_payment_input_conversion(self):
        """Test converting OrderInput data to PaymentInput."""
        order = OrderInput(
            order_id="ORD-100",
            customer_email="test@example.com",
            amount=250.00,
            items=[{"sku": "ITEM-1", "quantity": 1}],
        )

        # Extract payment information
        payment = PaymentInput(order_id=order.order_id, amount=order.amount)

        assert payment.order_id == order.order_id
        assert payment.amount == order.amount

    def test_payment_output_to_order_output_conversion(self):
        """Test incorporating PaymentOutput into OrderOutput."""
        payment_output = PaymentOutput(transaction_id="txn_abc123", status="completed")

        order_output = OrderOutput(
            order_id="ORD-200",
            status=payment_output.status,
            total_amount=99.99,
            message=f"Payment processed. Transaction: {payment_output.transaction_id}",
        )

        assert "txn_abc123" in order_output.message
        assert order_output.status == "completed"

    def test_models_json_roundtrip(self):
        """Test models can be serialized to JSON and back."""
        # Create original models
        order_input = OrderInput(
            order_id="ORD-300",
            customer_email="roundtrip@example.com",
            amount=175.50,
            items=[{"sku": "TEST-1", "quantity": 2}],
        )

        # Serialize to dict (JSON-compatible)
        data = order_input.model_dump()

        # Deserialize back
        restored = OrderInput(**data)

        assert restored.order_id == order_input.order_id
        assert restored.customer_email == order_input.customer_email
        assert restored.amount == order_input.amount
        assert restored.items == order_input.items
