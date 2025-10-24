"""
Tests for ParamSpec-based ActivitiesAPI with generated DTOs.

These tests verify:
1. Registration and exposure of Temporal-wrapped activities
2. Runtime validation of activity payloads
3. Optional result validation
4. Manifest generation
5. Error handling for invalid signatures
"""

import pytest
from pydantic import BaseModel, ValidationError

from src.app.core.services.tasks.temporal_engine import ActivitiesAPI, ActivityMeta


class TestActivitiesAPIRegistration:
    """Test activity registration and metadata."""

    def test_register_simple_activity(self):
        """Test registering a simple activity with typed parameters."""
        api = ActivitiesAPI()

        @api.register
        async def add(x: int, y: int) -> int:
            return x + y

        # Should have one registered activity
        assert len(api.get_registered()) == 1

        # Should have metadata
        meta = api.get_meta("add")
        assert meta.name == "add"
        assert meta.fn.__name__ == "add"
        assert meta.args_model is not None

        # Original function should be returned (preserving signature)
        assert add.__name__ == "add"

    def test_register_with_custom_name(self):
        """Test registering with a custom activity name."""
        api = ActivitiesAPI()

        @api.register(name="custom_name")
        async def my_func(x: int) -> int:
            return x * 2

        meta = api.get_meta("custom_name")
        assert meta.name == "custom_name"
        assert meta.fn.__name__ == "my_func"

    def test_register_with_result_model(self):
        """Test registering with result validation."""
        api = ActivitiesAPI()

        class Result(BaseModel):
            value: int
            message: str

        @api.register(result_model=Result)
        async def calculate(x: int) -> dict:
            return {"value": x * 2, "message": "success"}

        meta = api.get_meta("calculate")
        assert meta.result_model == Result

    def test_register_duplicate_name_raises_error(self):
        """Test that registering duplicate names raises ValueError."""
        api = ActivitiesAPI()

        @api.register
        async def func1() -> None:
            pass

        with pytest.raises(ValueError, match="already registered"):

            @api.register
            async def func1() -> None:  # Same name
                pass

    def test_register_without_decorator(self):
        """Test registering a function without decorator syntax."""
        api = ActivitiesAPI()

        async def my_activity(x: int, y: int) -> int:
            return x + y

        # Register directly
        registered_func = api.register(my_activity)

        assert registered_func.__name__ == "my_activity"
        assert len(api.get_registered()) == 1
        meta = api.get_meta("my_activity")
        assert meta.name == "my_activity"


class TestActivitiesAPIValidation:
    """Test runtime validation of activity arguments and results."""

    @pytest.mark.asyncio
    async def test_validates_correct_arguments(self):
        """Test that valid arguments pass validation."""
        api = ActivitiesAPI()

        @api.register
        async def add(x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("add")

        # Call wrapper with correct types
        result = await meta.wrapper(x=1, y=2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_validates_incorrect_arguments(self):
        """Test that invalid arguments raise ValidationError."""
        api = ActivitiesAPI()

        @api.register
        async def needs_int(x: int) -> int:
            return x + 1

        meta = api.get_meta("needs_int")

        # Call wrapper with wrong type
        with pytest.raises(ValidationError):
            await meta.wrapper(x="not-an-int")

    @pytest.mark.asyncio
    async def test_validates_missing_required_arguments(self):
        """Test that missing required arguments raise ValidationError."""
        api = ActivitiesAPI()

        @api.register
        async def requires_both(x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("requires_both")

        # Call wrapper with missing argument
        with pytest.raises(ValidationError):
            await meta.wrapper(x=1)  # Missing y

    @pytest.mark.asyncio
    async def test_validates_with_defaults(self):
        """Test validation with default parameter values."""
        api = ActivitiesAPI()

        @api.register
        async def with_default(x: int, y: int = 10) -> int:
            return x + y

        meta = api.get_meta("with_default")

        # Call with only required arg (should use default)
        result = await meta.wrapper(x=5)
        assert result == 15

        # Call with both args
        result = await meta.wrapper(x=5, y=3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_validates_result_when_model_provided(self):
        """Test that result validation works when model is provided."""
        api = ActivitiesAPI()

        class Result(BaseModel):
            value: int
            message: str

        @api.register(result_model=Result)
        async def returns_valid() -> dict:
            return {"value": 42, "message": "ok"}

        meta = api.get_meta("returns_valid")
        result = await meta.wrapper()
        assert result["value"] == 42

    @pytest.mark.asyncio
    async def test_validates_invalid_result(self):
        """Test that invalid results raise ValidationError."""
        api = ActivitiesAPI()

        class Result(BaseModel):
            value: int
            message: str

        @api.register(result_model=Result)
        async def returns_invalid() -> dict:
            return {"oops": True}  # Missing required fields

        meta = api.get_meta("returns_invalid")

        with pytest.raises(ValidationError):
            await meta.wrapper()

    @pytest.mark.asyncio
    async def test_skips_result_validation_when_none(self):
        """Test that None results don't trigger validation."""
        api = ActivitiesAPI()

        class Result(BaseModel):
            value: int

        @api.register(result_model=Result)
        async def returns_none() -> None:
            return None

        meta = api.get_meta("returns_none")
        result = await meta.wrapper()
        assert result is None  # Should not raise


class TestActivitiesAPISignatureSupport:
    """Test handling of different parameter kinds."""

    def test_supports_positional_or_keyword_params(self):
        """Test that standard parameters are supported."""
        api = ActivitiesAPI()

        @api.register
        async def standard(x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("standard")
        assert "x" in meta.args_model.model_fields
        assert "y" in meta.args_model.model_fields

    def test_supports_keyword_only_params(self):
        """Test that keyword-only parameters are supported."""
        api = ActivitiesAPI()

        @api.register
        async def keyword_only(*, x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("keyword_only")
        assert "x" in meta.args_model.model_fields
        assert "y" in meta.args_model.model_fields

    def test_rejects_positional_only_params(self):
        """Test that positional-only parameters raise TypeError."""
        api = ActivitiesAPI()

        with pytest.raises(TypeError, match="unsupported parameter kind"):

            @api.register
            async def positional_only(x: int, /, y: int) -> int:
                return x + y

    def test_rejects_var_positional(self):
        """Test that *args raises TypeError."""
        api = ActivitiesAPI()

        with pytest.raises(TypeError, match="unsupported parameter kind"):

            @api.register
            async def with_args(x: int, *args: int) -> int:
                return x

    def test_rejects_var_keyword(self):
        """Test that **kwargs raises TypeError."""
        api = ActivitiesAPI()

        with pytest.raises(TypeError, match="unsupported parameter kind"):

            @api.register
            async def with_kwargs(x: int, **kwargs: int) -> int:
                return x


class TestActivitiesAPIIntrospection:
    """Test introspection and manifest generation."""

    def test_get_meta_returns_metadata(self):
        """Test that get_meta returns correct metadata."""
        api = ActivitiesAPI()

        @api.register
        async def test_func(x: int, y: str) -> bool:
            return True

        meta = api.get_meta("test_func")
        assert isinstance(meta, ActivityMeta)
        assert meta.name == "test_func"
        assert callable(meta.fn)
        assert callable(meta.wrapper)
        assert callable(meta.temporal_fn)
        assert meta.args_model is not None
        assert meta.signature is not None

    def test_get_meta_raises_for_unknown_activity(self):
        """Test that get_meta raises KeyError for unknown activity."""
        api = ActivitiesAPI()

        with pytest.raises(KeyError, match="Unknown activity"):
            api.get_meta("nonexistent")

    def test_get_manifest_returns_schemas(self):
        """Test that get_manifest returns JSON-serializable schemas."""
        api = ActivitiesAPI()

        class Result(BaseModel):
            count: int

        @api.register(result_model=Result)
        async def count_items(category: str, limit: int = 10) -> dict:
            return {"count": limit}

        manifest = api.get_manifest()

        assert "count_items" in manifest
        activity_info = manifest["count_items"]

        # Should have args schema
        assert "args_schema" in activity_info
        assert activity_info["args_schema"]["type"] == "object"
        assert "category" in activity_info["args_schema"]["properties"]
        assert "limit" in activity_info["args_schema"]["properties"]

        # Should have result schema
        assert "result_schema" in activity_info
        assert activity_info["result_schema"]["type"] == "object"
        assert "count" in activity_info["result_schema"]["properties"]

        # Should have parameters list
        assert "parameters" in activity_info
        assert len(activity_info["parameters"]) == 2

        # Should have return annotation
        assert "return_annotation" in activity_info

    def test_get_manifest_handles_no_result_model(self):
        """Test manifest generation for activities without result models."""
        api = ActivitiesAPI()

        @api.register
        async def simple(x: int) -> int:
            return x * 2

        manifest = api.get_manifest()
        assert manifest["simple"]["result_schema"] is None

    def test_manifest_includes_all_registered_activities(self):
        """Test that manifest includes all activities."""
        api = ActivitiesAPI()

        @api.register
        async def activity1(x: int) -> int:
            return x

        @api.register
        async def activity2(y: str) -> str:
            return y

        @api.register
        async def activity3(z: bool) -> bool:
            return z

        manifest = api.get_manifest()
        assert len(manifest) == 3
        assert "activity1" in manifest
        assert "activity2" in manifest
        assert "activity3" in manifest


class TestActivitiesAPIArgBinding:
    """Test argument binding and zip_args functionality."""

    @pytest.mark.asyncio
    async def test_binds_positional_args(self):
        """Test that positional arguments are properly bound."""
        api = ActivitiesAPI()

        @api.register
        async def add(x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("add")

        # Call with positional args
        result = await meta.wrapper(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_binds_keyword_args(self):
        """Test that keyword arguments are properly bound."""
        api = ActivitiesAPI()

        @api.register
        async def add(x: int, y: int) -> int:
            return x + y

        meta = api.get_meta("add")

        # Call with keyword args
        result = await meta.wrapper(x=1, y=2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_binds_mixed_args(self):
        """Test that mixed positional and keyword args work."""
        api = ActivitiesAPI()

        @api.register
        async def concat(a: str, b: str, c: str) -> str:
            return f"{a}{b}{c}"

        meta = api.get_meta("concat")

        # Call with mixed args
        result = await meta.wrapper("x", b="y", c="z")
        assert result == "xyz"


class TestActivitiesAPIIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_registration_and_execution_flow(self):
        """Test complete flow from registration to execution."""
        api = ActivitiesAPI()

        # Define result model
        class EmailResult(BaseModel):
            message_id: str
            sent: bool

        # Register activity with validation
        @api.register(name="send_email", result_model=EmailResult)
        async def send_email(
            to: str, subject: str, body: str, retry: int = 0
        ) -> dict:
            return {
                "message_id": f"msg_{to}_{retry}",
                "sent": True,
            }

        # Verify registration
        assert len(api.get_registered()) == 1

        # Get metadata
        meta = api.get_meta("send_email")
        assert meta.name == "send_email"

        # Execute through wrapper (simulates worker execution)
        result = await meta.wrapper(
            to="user@test.com", subject="Test", body="Hello", retry=1
        )

        assert result["message_id"] == "msg_user@test.com_1"
        assert result["sent"] is True

    def test_temporal_functions_are_defn_wrapped(self):
        """Test that returned temporal functions are properly wrapped."""
        api = ActivitiesAPI()

        @api.register
        async def my_activity(x: int) -> int:
            return x

        temporal_funcs = api.get_registered()
        assert len(temporal_funcs) == 1

        # The temporal function should have activity metadata
        # (This is internal to Temporal, but we can verify it's callable)
        assert callable(temporal_funcs[0])
