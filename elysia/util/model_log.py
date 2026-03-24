"""
[ATHENA-CUSTOM] Async Supabase logger for LLM token usage.

Inserts records into the ``model_logs`` table via PostgREST after every
chat interaction.  Uses the same ``httpx`` pattern as supabase_client.py.
"""

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def _headers(service_role_key: str) -> dict[str, str]:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=minimal",
    }


async def resolve_model_id(
    provider: str,
    model: str,
    supabase_url: str,
    service_role_key: str,
) -> int | None:
    """
    Look up a model row in the ``models`` table by *provider* and *model*.

    Returns the row ``id`` (bigint) or ``None`` if not found.
    """
    url = (
        f"{supabase_url}/rest/v1/models"
        f"?provider=eq.{quote(provider)}"
        f"&model=eq.{quote(model)}"
        f"&select=id"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers(service_role_key))
            resp.raise_for_status()
            rows = resp.json()
            if rows and isinstance(rows, list) and len(rows) > 0:
                return rows[0].get("id")
            return None
    except Exception as exc:
        logger.warning(f"[MODEL-LOG] Failed to resolve model_id for {provider}/{model}: {exc}")
        return None


async def insert_model_log(
    model_id: int | None,
    input_tokens: int,
    output_tokens: int,
    user_id: str,
    reason: str,
    supabase_url: str,
    service_role_key: str,
) -> bool:
    """
    Insert a record into ``model_logs``.

    Returns ``True`` on success, ``False`` on failure.
    """
    payload: dict = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "user_id": user_id,
        "reason": reason,
    }
    if model_id is not None:
        payload["model_id"] = model_id

    url = f"{supabase_url}/rest/v1/model_logs"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers=_headers(service_role_key),
            )
            resp.raise_for_status()
            logger.info(
                f"[MODEL-LOG] Logged usage: model_id={model_id}, "
                f"in={input_tokens}, out={output_tokens}, "
                f"user={user_id}, reason={reason}"
            )
            return True
    except Exception as exc:
        logger.warning(f"[MODEL-LOG] Failed to insert model_log: {exc}")
        return False
