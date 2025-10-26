"""Unit tests for BaseWorkflow utility methods.

Tests the testable parts of BaseWorkflow that don't require Temporal runtime.
"""

import pytest

from src.app.worker.workflows.base import DEFAULT_ACTIVITY_OPTS


class TestDefaultActivityOptions:
    """Test default activity configuration options."""

    def test_default_activity_opts_has_start_to_close_timeout(self):
        """Test default options include start_to_close_timeout."""
        assert "start_to_close_timeout" in DEFAULT_ACTIVITY_OPTS

    def test_default_activity_opts_has_schedule_to_close_timeout(self):
        """Test default options include schedule_to_close_timeout."""
        assert "schedule_to_close_timeout" in DEFAULT_ACTIVITY_OPTS

    def test_default_activity_opts_has_retry_policy(self):
        """Test default options include retry_policy."""
        assert "retry_policy" in DEFAULT_ACTIVITY_OPTS

    def test_retry_policy_has_maximum_attempts(self):
        """Test retry policy specifies maximum attempts."""
        retry_policy = DEFAULT_ACTIVITY_OPTS["retry_policy"]
        assert hasattr(retry_policy, "maximum_attempts")
        assert retry_policy.maximum_attempts == 5

    def test_retry_policy_has_non_retryable_errors(self):
        """Test retry policy specifies non-retryable error types."""
        retry_policy = DEFAULT_ACTIVITY_OPTS["retry_policy"]
        assert hasattr(retry_policy, "non_retryable_error_types")
        assert "ValidationError" in retry_policy.non_retryable_error_types

    def test_timeouts_are_timedelta_objects(self):
        """Test timeout values are timedelta objects."""
        from datetime import timedelta

        start_to_close = DEFAULT_ACTIVITY_OPTS["start_to_close_timeout"]
        schedule_to_close = DEFAULT_ACTIVITY_OPTS["schedule_to_close_timeout"]

        assert isinstance(start_to_close, timedelta)
        assert isinstance(schedule_to_close, timedelta)

    def test_start_to_close_timeout_reasonable_value(self):
        """Test start_to_close_timeout is set to a reasonable value."""
        from datetime import timedelta

        timeout = DEFAULT_ACTIVITY_OPTS["start_to_close_timeout"]

        # Should be less than 5 minutes but more than 1 minute
        assert timeout < timedelta(minutes=5)
        assert timeout > timedelta(minutes=1)

    def test_schedule_to_close_timeout_reasonable_value(self):
        """Test schedule_to_close_timeout is set to a reasonable value."""
        from datetime import timedelta

        timeout = DEFAULT_ACTIVITY_OPTS["schedule_to_close_timeout"]

        # Should be around 5 minutes
        assert timeout == timedelta(minutes=5)

    def test_schedule_to_close_greater_than_start_to_close(self):
        """Test schedule_to_close is greater than or equal to start_to_close."""
        start_to_close = DEFAULT_ACTIVITY_OPTS["start_to_close_timeout"]
        schedule_to_close = DEFAULT_ACTIVITY_OPTS["schedule_to_close_timeout"]

        assert schedule_to_close >= start_to_close

    def test_default_opts_immutable_structure(self):
        """Test that default options have expected structure."""
        expected_keys = {
            "start_to_close_timeout",
            "schedule_to_close_timeout",
            "retry_policy",
        }

        actual_keys = set(DEFAULT_ACTIVITY_OPTS.keys())
        assert expected_keys == actual_keys

    def test_retry_policy_is_retry_policy_type(self):
        """Test retry_policy is the correct type."""
        from temporalio.common import RetryPolicy

        retry_policy = DEFAULT_ACTIVITY_OPTS["retry_policy"]
        assert isinstance(retry_policy, RetryPolicy)


class TestBaseWorkflowMetadata:
    """Test BaseWorkflow class metadata and structure."""

    def test_base_workflow_is_abstract(self):
        """Test BaseWorkflow cannot be instantiated directly."""
        from src.app.worker.workflows.base import BaseWorkflow

        # BaseWorkflow is abstract and should not be instantiable
        with pytest.raises(TypeError):
            BaseWorkflow()  # pyright: ignore[reportAbstractUsage]

    def test_base_workflow_has_run_method(self):
        """Test BaseWorkflow declares abstract run method."""
        from src.app.worker.workflows.base import BaseWorkflow

        assert hasattr(BaseWorkflow, "run")

    def test_base_workflow_has_state_query(self):
        """Test BaseWorkflow declares state query method."""
        from src.app.worker.workflows.base import BaseWorkflow

        assert hasattr(BaseWorkflow, "state")

    def test_base_workflow_has_cancel_signal(self):
        """Test BaseWorkflow declares cancel signal method."""
        from src.app.worker.workflows.base import BaseWorkflow

        assert hasattr(BaseWorkflow, "cancel")

    def test_base_workflow_has_start_workflow_classmethod(self):
        """Test BaseWorkflow has start_workflow class method."""
        from src.app.worker.workflows.base import BaseWorkflow

        assert hasattr(BaseWorkflow, "start_workflow")
        assert callable(getattr(BaseWorkflow, "start_workflow"))

    def test_base_workflow_generic_type_parameters(self):
        """Test BaseWorkflow uses generic type parameters."""
        from src.app.worker.workflows.base import BaseWorkflow

        # Check that it's a generic class
        assert hasattr(BaseWorkflow, "__orig_bases__")
