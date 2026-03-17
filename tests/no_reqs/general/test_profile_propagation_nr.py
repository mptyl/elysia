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


# --- Source-level checks: verify profile_context is used in all LLM-calling components ---

import inspect


def test_direct_answer_does_not_fetch_profile():
    """DirectAnswer should NOT call fetch_and_build_profile_prompt — it reads from TreeData."""
    from elysia.tools.text.direct_answer import DirectAnswer
    source = inspect.getsource(DirectAnswer.__call__)
    assert "fetch_and_build_profile_prompt" not in source
    assert "profile_context" in source


def test_forced_text_response_uses_profile_context():
    """ForcedTextResponse should pass profile_context when profile is available."""
    from elysia.tree.util import ForcedTextResponse
    source = inspect.getsource(ForcedTextResponse.__call__)
    assert "profile_context" in source


def test_decision_node_uses_profile_context():
    """DecisionNode should pass profile_context when creating decision_module."""
    from elysia.tree.util import DecisionNode
    source = inspect.getsource(DecisionNode.__call__)
    assert "profile_context" in source


def test_cited_summarizer_uses_profile_context():
    """CitedSummarizer should pass profile_context when profile is available."""
    from elysia.tools.text.text import CitedSummarizer
    source = inspect.getsource(CitedSummarizer.__call__)
    assert "profile_context" in source


def test_summarizer_uses_profile_context():
    """Summarizer should pass profile_context when profile is available."""
    from elysia.tools.text.text import Summarizer
    source = inspect.getsource(Summarizer.__call__)
    assert "profile_context" in source


def test_text_response_uses_profile_context():
    """TextResponse should pass profile_context when profile is available."""
    from elysia.tools.text.text import TextResponse
    source = inspect.getsource(TextResponse.__call__)
    assert "profile_context" in source


def test_summarise_items_uses_profile_context():
    """SummariseItems should use ElysiaChainOfThought with profile_context."""
    from elysia.tools.postprocessing.summarise_items import SummariseItems
    source = inspect.getsource(SummariseItems.__call__)
    assert "profile_context" in source
    assert "ElysiaChainOfThought" in source
