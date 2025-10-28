"""Unit tests for BaseWorkflow utility methods.

Tests the testable parts of BaseWorkflow that don't require Temporal runtime.
"""

import inspect

import pytest
from temporalio import workflow
from temporalio.client import Client

from src.app.worker.workflows.base import (
    default_activity_opts,
    default_workflow_opts,
)


class TestDefaultWorkflowOptions:
    """Test default workflow configuration options validation."""

    def test_default_workflow_opts_only_valid_keys(self):
        """Test default_workflow_opts only returns keys accepted by client.start_workflow."""
        # Get valid parameter names from client.start_workflow
        sig = inspect.signature(Client.start_workflow)
        valid_params = {
            param_name
            for param_name in sig.parameters.keys()
            if param_name not in ["self", "workflow", "arg", "args"]
        }

        # Get keys from default_workflow_opts
        opts = default_workflow_opts()
        actual_keys = set(opts.keys())

        # Assert all keys are valid
        invalid_keys = actual_keys - valid_params
        assert not invalid_keys, (
            f"default_workflow_opts() contains invalid keys: {invalid_keys}. "
            f"Valid keys for client.start_workflow: {valid_params}"
        )

    def test_default_workflow_opts_accepted_by_execute_workflow(self):
        """Test default_workflow_opts keys are also accepted by client.execute_workflow."""
        # Get valid parameter names from client.execute_workflow
        sig = inspect.signature(Client.execute_workflow)
        valid_params = {
            param_name
            for param_name in sig.parameters.keys()
            if param_name not in ["self", "workflow", "arg", "args"]
        }

        # Get keys from default_workflow_opts
        opts = default_workflow_opts()
        actual_keys = set(opts.keys())

        # Assert all keys are valid for execute_workflow too
        invalid_keys = actual_keys - valid_params
        assert not invalid_keys, (
            f"default_workflow_opts() contains keys not accepted by execute_workflow: {invalid_keys}. "
            f"Valid keys for client.execute_workflow: {valid_params}"
        )

    def test_default_workflow_opts_has_timeouts(self):
        """Test default_workflow_opts includes standard timeout parameters."""
        opts = default_workflow_opts()

        # These are the standard timeout keys we expect
        assert "execution_timeout" in opts
        assert "run_timeout" in opts
        assert "task_timeout" in opts

    def test_default_workflow_opts_has_retry_policy(self):
        """Test default_workflow_opts includes retry_policy."""
        opts = default_workflow_opts()
        assert "retry_policy" in opts

    def test_default_workflow_opts_timeouts_are_timedelta(self):
        """Test timeout values are timedelta objects."""
        from datetime import timedelta

        opts = default_workflow_opts()

        assert isinstance(opts["execution_timeout"], timedelta)
        assert isinstance(opts["run_timeout"], timedelta)
        assert isinstance(opts["task_timeout"], timedelta)

    def test_default_workflow_opts_retry_policy_type(self):
        """Test retry_policy is correct type."""
        from temporalio.common import RetryPolicy

        opts = default_workflow_opts()
        assert isinstance(opts["retry_policy"], RetryPolicy)


class TestDefaultActivityOptions:
    """Test default activity configuration options validation."""

    def test_default_activity_opts_only_valid_keys(self):
        """Test default_activity_opts only returns keys accepted by workflow.execute_activity."""
        # Get valid parameter names from workflow.execute_activity
        sig = inspect.signature(workflow.execute_activity)
        valid_params = {
            param_name
            for param_name in sig.parameters.keys()
            if param_name not in ["activity", "arg", "args"]
        }

        # Get keys from default_activity_opts
        opts = default_activity_opts()
        actual_keys = set(opts.keys())

        # Assert all keys are valid
        invalid_keys = actual_keys - valid_params
        assert not invalid_keys, (
            f"default_activity_opts() contains invalid keys: {invalid_keys}. "
            f"Valid keys for workflow.execute_activity: {valid_params}"
        )

    def test_default_activity_opts_has_start_to_close_timeout(self):
        """Test default options include start_to_close_timeout."""
        opts = default_activity_opts()
        assert "start_to_close_timeout" in opts

    def test_default_activity_opts_has_schedule_to_close_timeout(self):
        """Test default options include schedule_to_close_timeout."""
        opts = default_activity_opts()
        assert "schedule_to_close_timeout" in opts

    def test_default_activity_opts_has_retry_policy(self):
        """Test default options include retry_policy."""
        opts = default_activity_opts()
        assert "retry_policy" in opts

    def test_retry_policy_has_maximum_attempts(self):
        """Test retry policy specifies maximum attempts."""
        opts = default_activity_opts()
        retry_policy = opts["retry_policy"]
        assert hasattr(retry_policy, "maximum_attempts")
        assert retry_policy.maximum_attempts == 5

    def test_retry_policy_has_non_retryable_errors(self):
        """Test retry policy specifies non-retryable error types."""
        opts = default_activity_opts()
        retry_policy = opts["retry_policy"]
        assert hasattr(retry_policy, "non_retryable_error_types")
        assert "ValidationError" in retry_policy.non_retryable_error_types

    def test_timeouts_are_timedelta_objects(self):
        """Test timeout values are timedelta objects."""
        from datetime import timedelta

        opts = default_activity_opts()
        start_to_close = opts["start_to_close_timeout"]
        schedule_to_close = opts["schedule_to_close_timeout"]

        assert isinstance(start_to_close, timedelta)
        assert isinstance(schedule_to_close, timedelta)

    def test_start_to_close_timeout_reasonable_value(self):
        """Test start_to_close_timeout is set to a reasonable value."""
        from datetime import timedelta

        opts = default_activity_opts()
        timeout = opts["start_to_close_timeout"]

        # Should be a reasonable value (configured as 20 minutes in config)
        assert timeout > timedelta(seconds=0)
        assert timeout < timedelta(hours=1)

    def test_schedule_to_close_timeout_reasonable_value(self):
        """Test schedule_to_close_timeout is set to a reasonable value."""
        from datetime import timedelta

        opts = default_activity_opts()
        timeout = opts["schedule_to_close_timeout"]

        # Should be a reasonable value (configured as 1 hour in config)
        assert timeout > timedelta(seconds=0)
        assert timeout <= timedelta(hours=2)

    def test_schedule_to_close_greater_than_start_to_close(self):
        """Test schedule_to_close is greater than or equal to start_to_close."""
        opts = default_activity_opts()
        start_to_close = opts["start_to_close_timeout"]
        schedule_to_close = opts["schedule_to_close_timeout"]

        assert schedule_to_close >= start_to_close

    def test_default_opts_expected_structure(self):
        """Test that default options have expected structure."""
        expected_keys = {
            "start_to_close_timeout",
            "schedule_to_close_timeout",
            "retry_policy",
        }

        opts = default_activity_opts()
        actual_keys = set(opts.keys())
        assert expected_keys == actual_keys

    def test_retry_policy_is_retry_policy_type(self):
        """Test retry_policy is the correct type."""
        from temporalio.common import RetryPolicy

        opts = default_activity_opts()
        retry_policy = opts["retry_policy"]
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
        assert callable(BaseWorkflow.start_workflow)

    def test_base_workflow_generic_type_parameters(self):
        """Test BaseWorkflow uses generic type parameters."""
        from src.app.worker.workflows.base import BaseWorkflow

        # Check that it's a generic class
        assert hasattr(BaseWorkflow, "__orig_bases__")
