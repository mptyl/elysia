"""
[ATHENA-CUSTOM] Lightweight async Supabase PostgREST client.

Used to fetch user profile data for building personalized system prompts
in the DirectAnswer (non-RAG) path. Uses httpx to call the PostgREST API
with the service_role key (bypasses RLS).
"""

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def _headers(service_role_key: str) -> dict[str, str]:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Accept": "application/json",
    }


async def fetch_user_profile(
    user_id: str,
    supabase_url: str,
    service_role_key: str,
) -> dict | None:
    """
    Fetch a user profile with joined org_unit from Supabase.

    Returns the profile dict (with nested ``org_units`` object) or ``None``
    on any error.
    """
    url = (
        f"{supabase_url}/rest/v1/user_profiles"
        f"?id=eq.{quote(user_id)}"
        f"&select=*,org_units(*)"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers(service_role_key))
            resp.raise_for_status()
            rows = resp.json()
            if rows and isinstance(rows, list):
                return rows[0]
            return None
    except Exception as exc:
        logger.warning(f"[PROFILE-PROMPT] Failed to fetch user profile: {exc}")
        return None


async def fetch_role_instructions(
    department: str,
    job_title: str,
    supabase_url: str,
    service_role_key: str,
) -> str:
    """
    Fetch role-specific standard instructions for a department/job_title pair.

    Returns the instructions text, or empty string on miss/error.
    """
    url = (
        f"{supabase_url}/rest/v1/role_standard_instructions"
        f"?department=eq.{quote(department)}"
        f"&job_title=eq.{quote(job_title)}"
        f"&select=instructions"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers(service_role_key))
            resp.raise_for_status()
            rows = resp.json()
            if rows and isinstance(rows, list) and rows[0].get("instructions"):
                return rows[0]["instructions"]
            return ""
    except Exception as exc:
        logger.warning(f"[PROFILE-PROMPT] Failed to fetch role instructions: {exc}")
        return ""
