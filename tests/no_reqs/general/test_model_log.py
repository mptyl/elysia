"""
Tests for elysia.util.model_log — LLM token usage logging via PostgREST.

These tests mock httpx to avoid requiring a live Supabase instance.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from elysia.util.model_log import resolve_model_id, insert_model_log


# ---------------------------------------------------------------------------
# resolve_model_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_model_id_found():
    """resolve_model_id returns the id when the model exists."""
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 3}]
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = fake_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_model_id(
            provider="openrouter/google",
            model="gemini-3-flash-preview",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result == 3
    mock_client.get.assert_called_once()
    call_url = mock_client.get.call_args[0][0]
    assert "/rest/v1/models" in call_url
    assert "provider=eq." in call_url
    assert "model=eq." in call_url


@pytest.mark.asyncio
async def test_resolve_model_id_not_found():
    """resolve_model_id returns None when no model matches."""
    fake_response = MagicMock()
    fake_response.json.return_value = []
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = fake_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_model_id(
            provider="nonexistent",
            model="fake-model",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result is None


@pytest.mark.asyncio
async def test_resolve_model_id_error():
    """resolve_model_id returns None on network error."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_model_id(
            provider="openai",
            model="gpt-4o",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result is None


# ---------------------------------------------------------------------------
# insert_model_log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_model_log_success():
    """insert_model_log returns True on successful POST."""
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await insert_model_log(
            model_id=3,
            input_tokens=500,
            output_tokens=100,
            user_id="user-abc",
            reason="CHAT",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result is True
    mock_client.post.assert_called_once()

    # Verify the payload
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["model_id"] == 3
    assert payload["input_tokens"] == 500
    assert payload["output_tokens"] == 100
    assert payload["user_id"] == "user-abc"
    assert payload["reason"] == "CHAT"


@pytest.mark.asyncio
async def test_insert_model_log_null_model_id():
    """insert_model_log omits model_id from payload when it's None."""
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await insert_model_log(
            model_id=None,
            input_tokens=200,
            output_tokens=50,
            user_id="user-abc",
            reason="RAG",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result is True
    payload = mock_client.post.call_args.kwargs["json"]
    assert "model_id" not in payload
    assert payload["reason"] == "RAG"


@pytest.mark.asyncio
async def test_insert_model_log_failure():
    """insert_model_log returns False on network error."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("elysia.util.model_log.httpx.AsyncClient", return_value=mock_client):
        result = await insert_model_log(
            model_id=3,
            input_tokens=500,
            output_tokens=100,
            user_id="user-abc",
            reason="CHAT",
            supabase_url="http://localhost:8000",
            service_role_key="test-key",
        )

    assert result is False
