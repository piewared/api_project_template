"""Unit tests for HTTP dependencies."""

import pytest
from unittest.mock import Mock
from fastapi import HTTPException, Request

from src.api.http.deps import require_scope, require_role


class TestScopeDependency:
    """Test the require_scope dependency function."""

    @pytest.mark.asyncio
    async def test_allows_request_with_required_scope(self):
        """Should allow requests when required scope is present."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.scopes = {"read", "write", "admin"}
        
        scope_dep = require_scope("read")
        
        # Should not raise
        await scope_dep(request)

    @pytest.mark.asyncio
    async def test_blocks_request_without_required_scope(self):
        """Should block requests when required scope is missing."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.scopes = {"write"}
        
        scope_dep = require_scope("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_blocks_request_with_no_scopes(self):
        """Should block requests when no scopes are set."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.scopes = set()
        
        scope_dep = require_scope("read")
        
        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "read" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_blocks_request_without_state_scopes(self):
        """Should block requests when scopes attribute is missing."""
        request = Mock(spec=Request)
        # Create a simple object without the scopes attribute
        class SimpleState:
            pass
        request.state = SimpleState()
        
        scope_dep = require_scope("read")
        
        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "Missing required scope: read" in str(exc_info.value.detail)
class TestRoleDependency:
    """Test the require_role dependency function."""

    @pytest.mark.asyncio
    async def test_allows_request_with_required_role(self):
        """Should allow requests when required role is present."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.roles = {"user", "admin", "moderator"}
        
        role_dep = require_role("admin")
        
        # Should not raise
        await role_dep(request)

    @pytest.mark.asyncio
    async def test_blocks_request_without_required_role(self):
        """Should block requests when required role is missing."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.roles = {"user"}
        
        role_dep = require_role("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_blocks_request_with_no_roles(self):
        """Should block requests when no roles are set."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.roles = set()
        
        role_dep = require_role("user")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "user" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_blocks_request_without_state_roles(self):
        """Should block requests when roles attribute is missing."""
        request = Mock(spec=Request)
        # Create a simple object without the roles attribute
        class SimpleState:
            pass
        request.state = SimpleState()
        
        role_dep = require_role("user")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)
        
        assert exc_info.value.status_code == 403
        assert "Missing required role: user" in str(exc_info.value.detail)