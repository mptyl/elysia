"""
Tests for user profile context propagation (no external dependencies).
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from elysia.api.services.user import UserManager


@pytest.mark.asyncio
async def test_initialise_tree_populates_profile_system_prompt():
    """After initialise_tree, tree_data.profile_system_prompt should contain the cached profile."""
    user_id = f"test_{uuid4()}"
    conversation_id = f"test_{uuid4()}"
    fake_profile_prompt = "<profile-system-prompt>fake</profile-system-prompt>"

    with patch(
        "elysia.api.services.user.fetch_and_build_profile_prompt",
        new_callable=AsyncMock,
        return_value=fake_profile_prompt,
    ):
        user_manager = UserManager()
        tree = await user_manager.initialise_tree(user_id, conversation_id, low_memory=True)
        assert tree.tree_data.profile_system_prompt == fake_profile_prompt


@pytest.mark.asyncio
async def test_initialise_tree_caches_profile_across_conversations():
    """Profile should be fetched once per user, reused across conversations."""
    user_id = f"test_{uuid4()}"
    conv_1 = f"test_{uuid4()}"
    conv_2 = f"test_{uuid4()}"
    fake_profile_prompt = "<profile-system-prompt>cached</profile-system-prompt>"

    mock_fetch = AsyncMock(return_value=fake_profile_prompt)

    with patch(
        "elysia.api.services.user.fetch_and_build_profile_prompt",
        mock_fetch,
    ):
        user_manager = UserManager()
        tree1 = await user_manager.initialise_tree(user_id, conv_1, low_memory=True)
        tree2 = await user_manager.initialise_tree(user_id, conv_2, low_memory=True)

        assert tree1.tree_data.profile_system_prompt == fake_profile_prompt
        assert tree2.tree_data.profile_system_prompt == fake_profile_prompt
        # Should only fetch once (cached at user level)
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_initialise_tree_graceful_degradation():
    """When profile fetch returns empty, tree should still work with empty profile."""
    user_id = f"test_{uuid4()}"
    conversation_id = f"test_{uuid4()}"

    with patch(
        "elysia.api.services.user.fetch_and_build_profile_prompt",
        new_callable=AsyncMock,
        return_value="",
    ):
        user_manager = UserManager()
        tree = await user_manager.initialise_tree(user_id, conversation_id, low_memory=True)
        assert tree.tree_data.profile_system_prompt == ""


@pytest.mark.asyncio
async def test_initialise_tree_handles_fetch_exception():
    """When profile fetch raises, initialise_tree should catch and default to empty string."""
    user_id = f"test_{uuid4()}"
    conversation_id = f"test_{uuid4()}"

    with patch(
        "elysia.api.services.user.fetch_and_build_profile_prompt",
        new_callable=AsyncMock,
        side_effect=Exception("Supabase connection failed"),
    ):
        user_manager = UserManager()
        tree = await user_manager.initialise_tree(user_id, conversation_id, low_memory=True)
        assert tree.tree_data.profile_system_prompt == ""
