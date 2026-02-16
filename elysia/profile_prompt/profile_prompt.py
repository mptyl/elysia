"""
[ATHENA-CUSTOM] Profile prompt builder.

Loads the XML system-prompt template from disk (cached), substitutes user
profile placeholders, and returns the rendered text to be injected into
the DirectAnswer LLM call.

Follows the same pattern as ``elysia.guardrails.ethical_guard``.
"""

import logging
from functools import lru_cache
from pathlib import Path

from elysia.util.supabase_client import fetch_user_profile, fetch_role_instructions

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Default values when profile fields are missing
_DEFAULTS = {
    "job_title": "",
    "department": "",
    "org_unit_name": "",
    "response_detail_level": "balanced",
    "communication_tone": "professional",
    "preferred_language": "it",
    "response_focus": "technical",
    "role_standard_instructions": "",
    "custom_instructions": "",
    "custom_instructions_mode": "append",
}


@lru_cache(maxsize=None)
def _load_template() -> str:
    """Load the profile system prompt XML template. Cached in memory."""
    filepath = PROMPTS_DIR / "profile_system_prompt.xml"
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("[PROFILE-PROMPT] Template file not found: %s", filepath)
        return ""


def build_profile_system_prompt(
    profile: dict,
    role_instructions: str = "",
) -> str:
    """
    Render the profile system prompt by substituting placeholders in the
    XML template with actual user profile values.

    Args:
        profile: User profile dict from Supabase (with nested ``org_units``).
        role_instructions: Role-specific standard instructions text.

    Returns:
        The rendered system prompt string, or empty string if template is
        missing.
    """
    template = _load_template()
    if not template:
        return ""

    # Extract org_unit name from nested join
    org_unit = profile.get("org_units") or {}
    org_unit_name = org_unit.get("name", _DEFAULTS["org_unit_name"])

    custom_instructions = profile.get("custom_instructions", _DEFAULTS["custom_instructions"])
    custom_instructions_mode = profile.get(
        "custom_instructions_mode", _DEFAULTS["custom_instructions_mode"]
    )

    # Handle override mode: custom_instructions replace role_instructions entirely
    effective_role_instructions = role_instructions
    if custom_instructions_mode == "override" and custom_instructions:
        effective_role_instructions = ""

    values = {
        "job_title": profile.get("job_title") or _DEFAULTS["job_title"],
        "department": profile.get("department") or _DEFAULTS["department"],
        "org_unit_name": org_unit_name,
        "response_detail_level": profile.get("response_detail_level", _DEFAULTS["response_detail_level"]),
        "communication_tone": profile.get("communication_tone", _DEFAULTS["communication_tone"]),
        "preferred_language": profile.get("preferred_language", _DEFAULTS["preferred_language"]),
        "response_focus": profile.get("response_focus", _DEFAULTS["response_focus"]),
        "role_standard_instructions": effective_role_instructions,
        "custom_instructions": custom_instructions,
        "custom_instructions_mode": custom_instructions_mode,
    }

    try:
        return template.format(**values)
    except KeyError as exc:
        logger.warning("[PROFILE-PROMPT] Missing placeholder in template: %s", exc)
        return ""


async def fetch_and_build_profile_prompt(
    user_id: str,
    settings,
) -> str:
    """
    End-to-end: fetch user profile from Supabase, fetch role instructions,
    and build the rendered system prompt.

    Fail-open: returns empty string if Supabase is not configured, user
    profile is not found, or any error occurs.

    Args:
        user_id: The Supabase auth user UUID.
        settings: Elysia Settings instance (needs ``SUPABASE_URL`` and
            ``SUPABASE_SERVICE_ROLE_KEY``).

    Returns:
        Rendered profile system prompt, or empty string.
    """
    supabase_url = getattr(settings, "SUPABASE_URL", "")
    service_role_key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_role_key:
        return ""

    profile = await fetch_user_profile(user_id, supabase_url, service_role_key)
    if not profile:
        return ""

    # Fetch role-specific instructions based on department + job_title
    department = profile.get("department") or ""
    job_title = profile.get("job_title") or ""

    role_instructions = ""
    if department and job_title:
        role_instructions = await fetch_role_instructions(
            department, job_title, supabase_url, service_role_key
        )

    prompt = build_profile_system_prompt(profile, role_instructions)

    if prompt:
        logger.info(
            "[PROFILE-PROMPT] Built profile prompt for user=%s dept=%s title=%s",
            user_id,
            department,
            job_title,
        )

    return prompt
