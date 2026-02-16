"""
[ATHENA-CUSTOM] Profile-based system prompt for non-RAG LLM calls.

Loads an XML template from the filesystem and fills it with user profile data
fetched from Supabase. The rendered prompt personalizes DirectAnswer responses.
"""

from elysia.profile_prompt.profile_prompt import (
    build_profile_system_prompt,
    fetch_and_build_profile_prompt,
)

__all__ = ["build_profile_system_prompt", "fetch_and_build_profile_prompt"]
