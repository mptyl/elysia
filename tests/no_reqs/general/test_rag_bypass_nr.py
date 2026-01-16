import pytest
import asyncio
from elysia.config import Settings
from elysia.tree.tree import Tree
from elysia.util.client import ClientManager

@pytest.mark.asyncio
async def test_disable_rag_initialization():
    settings = Settings()
    settings.configure(
        base_model="gpt-4o-mini",
        base_provider="openai",
        complex_model="gpt-4o",
        complex_provider="openai",
    )
    tree = Tree(settings=settings)
    
    # Run async_run with disable_rag=True
    gen = tree.async_run(
        user_prompt="Hello",
        disable_rag=True, 
        close_clients_after_completion=False
    )
    
    # Iterate once to trigger initialization
    async for _ in gen:
        break
        
    # Verify rag_enabled is False
    assert tree.tree_data.rag_enabled is False
    
    # Verify DirectAnswer availability
    # It should be available regardless effectively, but let's check
    assert "direct_answer" in tree.tools
    is_da_available = await tree.tools["direct_answer"].is_tool_available(
        tree_data=tree.tree_data,
        base_lm=tree.base_lm,
        complex_lm=tree.complex_lm,
        client_manager=None
    )
    assert is_da_available is True
    
    # Verify Query unavailable
    is_query_available = await tree.tools["query"].is_tool_available(
        tree_data=tree.tree_data,
        base_lm=tree.base_lm,
        complex_lm=tree.complex_lm,
        client_manager=ClientManager(
            wcd_url=settings.WCD_URL, wcd_api_key=settings.WCD_API_KEY
        )
    )
    assert is_query_available is False

@pytest.mark.asyncio
async def test_enable_rag_initialization():
    settings = Settings()
    settings.configure(
        base_model="gpt-4o-mini",
        base_provider="openai",
        complex_model="gpt-4o",
        complex_provider="openai",
    )
    tree = Tree(settings=settings)
    
    # Run async_run with disable_rag=False (default)
    gen = tree.async_run(
        user_prompt="Hello",
        disable_rag=False,
        close_clients_after_completion=False
    )
    
    async for _ in gen:
        break
        
    # Verify rag_enabled is True
    assert tree.tree_data.rag_enabled is True
