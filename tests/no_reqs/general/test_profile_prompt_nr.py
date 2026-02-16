"""
Tests for the profile prompt builder module (no external dependencies).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from elysia.profile_prompt.profile_prompt import (
    build_profile_system_prompt,
    fetch_and_build_profile_prompt,
    _load_template,
)


# --- Fixtures ---

@pytest.fixture
def sample_profile():
    return {
        "id": "test-user-uuid",
        "job_title": "Technical Project Manager",
        "department": "IES",
        "response_detail_level": "executive_summary",
        "communication_tone": "direct",
        "preferred_language": "it",
        "response_focus": "managerial",
        "custom_instructions": "Always include a summary table.",
        "custom_instructions_mode": "append",
        "org_units": {
            "id": "org-uuid",
            "name": "Default",
            "ai_identity_base": "Default organizational context",
        },
    }


@pytest.fixture
def minimal_profile():
    """Profile with only required fields, missing optional ones."""
    return {
        "id": "test-user-uuid",
        "org_units": None,
    }


# --- Template loading ---

def test_load_template_returns_nonempty():
    template = _load_template()
    assert template, "Template should be loaded from disk"
    assert "{job_title}" in template
    assert "{response_detail_level}" in template
    assert "<profile-system-prompt>" in template


# --- build_profile_system_prompt ---

def test_build_full_profile(sample_profile):
    result = build_profile_system_prompt(sample_profile, role_instructions="Focus on PM.")
    assert "Technical Project Manager" in result
    assert "IES" in result
    assert "Default" in result  # org_unit_name
    assert "executive_summary" in result
    assert "direct" in result
    assert "managerial" in result
    assert "Focus on PM." in result
    assert "Always include a summary table." in result
    assert 'mode="append"' in result


def test_build_minimal_profile(minimal_profile):
    result = build_profile_system_prompt(minimal_profile)
    assert result, "Should still render with defaults"
    assert "balanced" in result  # default detail level
    assert "professional" in result  # default tone


def test_build_override_mode_clears_role_instructions(sample_profile):
    sample_profile["custom_instructions_mode"] = "override"
    sample_profile["custom_instructions"] = "My custom instructions only."
    result = build_profile_system_prompt(
        sample_profile, role_instructions="This should be cleared."
    )
    assert "This should be cleared." not in result
    assert "My custom instructions only." in result
    assert 'mode="override"' in result


def test_build_override_mode_empty_custom_keeps_role(sample_profile):
    """If override mode but custom_instructions is empty, role_instructions should remain."""
    sample_profile["custom_instructions_mode"] = "override"
    sample_profile["custom_instructions"] = ""
    result = build_profile_system_prompt(
        sample_profile, role_instructions="Keep me."
    )
    assert "Keep me." in result


def test_build_empty_profile():
    result = build_profile_system_prompt({})
    assert result, "Should render with all defaults"


# --- fetch_and_build_profile_prompt (async tests via asyncio.run) ---

def test_fetch_and_build_no_supabase_config():
    """Returns empty string when Supabase is not configured."""
    settings = MagicMock()
    settings.SUPABASE_URL = ""
    settings.SUPABASE_SERVICE_ROLE_KEY = ""
    result = asyncio.run(fetch_and_build_profile_prompt("user-id", settings))
    assert result == ""


def test_fetch_and_build_profile_not_found():
    """Returns empty string when user profile is not found."""
    settings = MagicMock()
    settings.SUPABASE_URL = "http://localhost:8000"
    settings.SUPABASE_SERVICE_ROLE_KEY = "test-key"

    with patch(
        "elysia.profile_prompt.profile_prompt.fetch_user_profile",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = asyncio.run(fetch_and_build_profile_prompt("user-id", settings))
        assert result == ""


def test_fetch_and_build_success(sample_profile):
    """Full successful flow."""
    settings = MagicMock()
    settings.SUPABASE_URL = "http://localhost:8000"
    settings.SUPABASE_SERVICE_ROLE_KEY = "test-key"

    with patch(
        "elysia.profile_prompt.profile_prompt.fetch_user_profile",
        new_callable=AsyncMock,
        return_value=sample_profile,
    ), patch(
        "elysia.profile_prompt.profile_prompt.fetch_role_instructions",
        new_callable=AsyncMock,
        return_value="Role-specific instructions here.",
    ):
        result = asyncio.run(fetch_and_build_profile_prompt("test-user-uuid", settings))
        assert "Technical Project Manager" in result
        assert "Role-specific instructions here." in result
