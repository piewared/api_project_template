"""Unit tests for the async context manager system."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from src.app.runtime.config import (
    AppContext,
    ApplicationConfig,
    get_config,
    get_context,
    set_context,
    with_context,
)


class TestContextManager:
    """Test the context manager functionality."""

    def test_default_context_available(self):
        """Should have a default context available."""
        context = get_context()
        config = get_config()

        assert isinstance(context, AppContext)
        assert isinstance(config, ApplicationConfig)
        assert context.config is config

    def test_with_context_override_single_level(self):
        """Should override config for the duration of the context manager."""
        original_config = get_config()
        original_uid_claim = original_config.jwt.uid_claim

        # Create test config with different value
        test_config = ApplicationConfig()
        test_config.jwt.uid_claim = "custom_uid"

        with with_context(test_config):
            override_config = get_config()
            assert override_config.jwt.uid_claim == "custom_uid"
            assert override_config is not original_config

        # Should revert after context
        after_config = get_config()
        assert after_config.jwt.uid_claim == original_uid_claim
        assert after_config is original_config

    def test_with_context_nested_overrides(self):
        """Should handle nested context overrides correctly."""
        original_config = get_config()
        original_uid_claim = original_config.jwt.uid_claim

        # First level override
        level1_config = ApplicationConfig()
        level1_config.jwt.uid_claim = "level1_uid"
        level1_config.environment = "production"

        with with_context(level1_config):
            level1_context = get_config()
            assert level1_context.jwt.uid_claim == "level1_uid"
            assert level1_context.environment == "production"

            # Second level override
            level2_config = ApplicationConfig()
            level2_config.jwt.uid_claim = "level2_uid"
            level2_config.environment = "test"
            level2_config.log_level = "DEBUG"

            with with_context(level2_config):
                level2_context = get_config()
                assert level2_context.jwt.uid_claim == "level2_uid"
                assert level2_context.environment == "test"
                assert level2_context.log_level == "DEBUG"

                # Third level override
                level3_config = ApplicationConfig()
                level3_config.jwt.uid_claim = "level3_uid"
                level3_config.database_url = "sqlite:///level3.db"

                with with_context(level3_config):
                    level3_context = get_config()
                    assert level3_context.jwt.uid_claim == "level3_uid"
                    assert level3_context.database_url == "sqlite:///level3.db"

                # Back to level 2
                back_to_level2 = get_config()
                assert back_to_level2.jwt.uid_claim == "level2_uid"
                assert back_to_level2.environment == "test"
                assert back_to_level2.log_level == "DEBUG"

            # Back to level 1
            back_to_level1 = get_config()
            assert back_to_level1.jwt.uid_claim == "level1_uid"
            assert back_to_level1.environment == "production"

        # Back to original
        final_config = get_config()
        assert final_config.jwt.uid_claim == original_uid_claim
        assert final_config is original_config

    def test_with_context_no_override(self):
        """Should work without any override (current context)."""
        original_config = get_config()

        with with_context():
            context_config = get_config()
            assert context_config is original_config

        after_config = get_config()
        assert after_config is original_config

    def test_context_isolation_in_nested_calls(self):

        def inner_function() -> str:
            """Function that reads config in different context."""
            return get_config().jwt.uid_claim

        def middle_function() -> tuple[str, str]:
            """Function that creates its own context and calls inner."""
            middle_config = ApplicationConfig()
            middle_config.jwt.uid_claim = "middle_uid"

            with with_context(middle_config):
                return inner_function(), get_config().environment

        # Set up outer context
        outer_config = ApplicationConfig()
        outer_config.jwt.uid_claim = "outer_uid"
        outer_config.environment = "production"

        with with_context(outer_config):
            # Call middle function which creates its own context
            middle_uid, middle_env = middle_function()

            # Middle function should see its own uid but inherit environment
            # (inheritance means child inherits parent's non-overridden values)
            assert middle_uid == "middle_uid"
            assert middle_env == "production"  # Inherited from outer context

            # After middle function, should be back to outer context
            assert get_config().jwt.uid_claim == "outer_uid"
            assert get_config().environment == "production"

    def test_exception_handling_in_context(self):
        """Should properly restore context even when exceptions occur."""
        original_config = get_config()
        original_uid_claim = original_config.jwt.uid_claim

        test_config = ApplicationConfig()
        test_config.jwt.uid_claim = "exception_test_uid"

        try:
            with with_context(test_config):
                assert get_config().jwt.uid_claim == "exception_test_uid"
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        # Should restore original context even after exception
        after_config = get_config()
        assert after_config.jwt.uid_claim == original_uid_claim
        assert after_config is original_config

    def test_context_manager_with_different_config_properties(self):
        """Should handle overriding different configuration properties."""
        original_config = get_config()

        test_config = ApplicationConfig()
        test_config.environment = "test"
        test_config.log_level = "DEBUG"
        test_config.database_url = "sqlite:///test.db"
        test_config.jwt.uid_claim = "test_uid"
        test_config.jwt.clock_skew = 30
        test_config.session.max_age = 1800

        with with_context(test_config):
            override_config = get_config()

            assert override_config.environment == "test"
            assert override_config.log_level == "DEBUG"
            assert override_config.database_url == "sqlite:///test.db"
            assert override_config.jwt.uid_claim == "test_uid"
            assert override_config.jwt.clock_skew == 30
            assert override_config.session.max_age == 1800

        # All should revert
        after_config = get_config()
        assert after_config is original_config


class TestAsyncContextManager:
    """Test context manager behavior in async contexts."""

    @pytest.mark.asyncio
    async def test_async_context_isolation(self):
        """Should maintain context isolation in async functions."""
        original_config = get_config()

        async def async_worker(worker_id: str) -> str:
            """Async worker that creates its own context."""
            worker_config = ApplicationConfig()
            worker_config.jwt.uid_claim = f"worker_{worker_id}_uid"

            with with_context(worker_config):
                # Simulate some async work
                await asyncio.sleep(0.01)
                return get_config().jwt.uid_claim

        # Run multiple async workers concurrently
        tasks = [async_worker(str(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Each worker should see its own context
        expected = [f"worker_{i}_uid" for i in range(5)]
        assert results == expected

        # Original context should be unchanged
        assert get_config() is original_config

    @pytest.mark.asyncio
    async def test_async_nested_contexts(self):
        """Should handle nested contexts in async functions."""
        original_config = get_config()

        async def level2_async() -> tuple[str, str]:
            """Second level async function with its own context."""
            level2_config = ApplicationConfig()
            level2_config.jwt.uid_claim = "level2_async_uid"

            with with_context(level2_config):
                await asyncio.sleep(0.01)
                return get_config().jwt.uid_claim, get_config().environment

        # Level 1 context
        level1_config = ApplicationConfig()
        level1_config.jwt.uid_claim = "level1_async_uid"
        level1_config.environment = "production"

        with with_context(level1_config):
            # Should see level 1 context
            assert get_config().jwt.uid_claim == "level1_async_uid"
            assert get_config().environment == "production"

            # Call level 2 async function
            uid, env = await level2_async()

            # Level 2 should see its own uid but inherit environment
            # (inheritance means child inherits parent's non-overridden values)
            assert uid == "level2_async_uid"
            assert env == "production"  # Inherited from level 1 context

            # Back to level 1 after async call
            assert get_config().jwt.uid_claim == "level1_async_uid"
            assert get_config().environment == "production"

        # Back to original
        assert get_config() is original_config

    @pytest.mark.asyncio
    async def test_async_context_with_concurrent_tasks(self):
        """Should maintain context isolation with concurrent async tasks."""
        results = {}

        # Valid environments to cycle through
        valid_envs = ["development", "production", "test"]

        async def async_task(task_id: int) -> None:
            """Async task that works in its own context."""
            task_config = ApplicationConfig()
            task_config.jwt.uid_claim = f"task_{task_id}_uid"
            # Cycle through valid environments
            env_index = task_id % len(valid_envs)
            if env_index == 0:
                task_config.environment = "development"
            elif env_index == 1:
                task_config.environment = "production"
            else:
                task_config.environment = "test"

            with with_context(task_config):
                # Simulate varying amounts of async work
                await asyncio.sleep(0.01 * task_id)

                # Store results from this task's context
                results[task_id] = {
                    "uid": get_config().jwt.uid_claim,
                    "env": get_config().environment,
                }

        # Start multiple concurrent tasks
        tasks = [async_task(i) for i in range(1, 6)]
        await asyncio.gather(*tasks)

        # Each task should have seen its own context
        for i in range(1, 6):
            assert results[i]["uid"] == f"task_{i}_uid"
            expected_env = valid_envs[i % len(valid_envs)]
            assert results[i]["env"] == expected_env


class TestThreadSafety:
    """Test context manager behavior across threads."""

    def test_thread_isolation(self):
        """Should maintain context isolation across threads."""
        original_config = get_config()
        results = {}

        # Valid environments to cycle through
        valid_envs = ["development", "production", "test"]

        def thread_worker(worker_id: int) -> None:
            """Worker function that runs in its own thread."""
            worker_config = ApplicationConfig()
            worker_config.jwt.uid_claim = f"thread_{worker_id}_uid"
            # Cycle through valid environments
            env_index = worker_id % len(valid_envs)
            if env_index == 0:
                worker_config.environment = "development"
            elif env_index == 1:
                worker_config.environment = "production"
            else:
                worker_config.environment = "test"

            with with_context(worker_config):
                # Simulate some work
                import time

                time.sleep(0.01)

                # Store results from this thread's context
                results[worker_id] = {
                    "uid": get_config().jwt.uid_claim,
                    "env": get_config().environment,
                }

        # Run workers in separate threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(thread_worker, i) for i in range(1, 6)]

            # Wait for all threads to complete
            for future in futures:
                future.result()

        # Each thread should have seen its own context
        for i in range(1, 6):
            assert results[i]["uid"] == f"thread_{i}_uid"
            assert results[i]["env"] == valid_envs[i % len(valid_envs)]

        # Main thread context should be unchanged
        assert get_config() is original_config

    def test_mixed_async_and_thread_contexts(self):
        """Should handle mixed async and thread contexts correctly."""
        import threading
        import time

        results = []

        def thread_function():
            """Function that runs in a separate thread."""
            thread_config = ApplicationConfig()
            thread_config.jwt.uid_claim = "thread_uid"

            with with_context(thread_config):
                time.sleep(0.02)  # Simulate work
                results.append(("thread", get_config().jwt.uid_claim))

        # Start thread context
        main_config = ApplicationConfig()
        main_config.jwt.uid_claim = "main_uid"

        with with_context(main_config):
            # Record main thread context
            results.append(("main_before", get_config().jwt.uid_claim))

            # Start separate thread
            thread = threading.Thread(target=thread_function)
            thread.start()

            # Record main thread context while thread is running
            results.append(("main_during", get_config().jwt.uid_claim))

            # Wait for thread to complete
            thread.join()

            # Record main thread context after thread completes
            results.append(("main_after", get_config().jwt.uid_claim))

        # Verify results
        expected = [
            ("main_before", "main_uid"),
            ("main_during", "main_uid"),
            ("thread", "thread_uid"),
            ("main_after", "main_uid"),
        ]

        # Sort by context name for consistent comparison
        results.sort()
        expected.sort()
        assert results == expected


class TestContextManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_rapid_context_switching(self):
        """Should handle rapid context switching correctly."""
        original_config = get_config()

        configs = []
        for i in range(100):
            config = ApplicationConfig()
            config.jwt.uid_claim = f"rapid_{i}"
            configs.append(config)

        # Rapidly switch contexts
        for i, config in enumerate(configs):
            with with_context(config):
                assert get_config().jwt.uid_claim == f"rapid_{i}"

        # Should be back to original
        assert get_config() is original_config

    def test_deeply_nested_contexts(self):
        """Should handle deeply nested contexts without stack overflow."""
        original_config = get_config()
        depth = 50  # Deep nesting

        def create_nested_context(level: int) -> str:
            """Recursively create nested contexts."""
            if level == 0:
                return get_config().jwt.uid_claim

            config = ApplicationConfig()
            config.jwt.uid_claim = f"deep_{level}"

            with with_context(config):
                return create_nested_context(level - 1)

        result = create_nested_context(depth)
        assert result == "deep_1"  # Deepest level

        # Should be back to original
        assert get_config() is original_config

    def test_context_manager_reentrance(self):
        """Should handle reentrant context manager calls."""
        original_config = get_config()

        test_config = ApplicationConfig()
        test_config.jwt.uid_claim = "reentrant_uid"

        with with_context(test_config):
            assert get_config().jwt.uid_claim == "reentrant_uid"

            # Reentrant call with same config
            with with_context(test_config):
                assert get_config().jwt.uid_claim == "reentrant_uid"

                # Another level
                with with_context(test_config):
                    assert get_config().jwt.uid_claim == "reentrant_uid"

        # Should be back to original
        assert get_config() is original_config

    def test_context_inheritance_partial_override(self):
        """Should properly inherit non-overridden properties from parent context."""

        # Parent context sets multiple properties
        parent_config = ApplicationConfig()
        parent_config.jwt.uid_claim = "parent_uid"
        parent_config.environment = "production"
        parent_config.log_level = "DEBUG"
        parent_config.database_url = "sqlite:///parent.db"

        with with_context(parent_config):
            # Child context only overrides some properties
            child_config = ApplicationConfig()
            child_config.jwt.uid_claim = "child_uid"  # Override
            # Don't set environment, log_level, database_url - should inherit

            with with_context(child_config):
                child_context = get_config()

                # Should see overridden property
                assert child_context.jwt.uid_claim == "child_uid"

                # Should inherit parent's non-overridden properties
                # Note: This tests proper inheritance behavior where child contexts
                # inherit non-overridden values from their parent context
                assert (
                    child_context.environment == "production"
                )  # Inherited from parent
                assert child_context.log_level == "DEBUG"  # Inherited from parent

            # Back to parent context
            parent_context = get_config()
            assert parent_context.jwt.uid_claim == "parent_uid"
            assert parent_context.environment == "production"
            assert parent_context.log_level == "DEBUG"
