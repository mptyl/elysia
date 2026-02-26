"""
Routes for serving the static frontend build.

Provides:
- Reverse proxies: /supabase/*, /entra/*, /common/*
- Auth routes: /api/auth/authorize, /api/auth/session, /api/auth/signout,
  /api/auth/sync-profile, /auth/callback

These replicate what Next.js handles in server mode (rewrites + API routes).
Only used when the frontend is built as a static export and served by FastAPI.
"""

import base64
import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration (mirrors elysia-frontend/.env.local)
# ---------------------------------------------------------------------------

SUPABASE_INTERNAL_URL = os.getenv("SUPABASE_INTERNAL_URL", "http://127.0.0.1:8000")
SUPABASE_ANON_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "")
AUTH_COOKIE_NAME = os.getenv("NEXT_PUBLIC_SUPABASE_AUTH_COOKIE_NAME", "sb-athena-auth-token")

ENTRA_INTERNAL_URL = os.getenv("ENTRA_INTERNAL_URL", "http://127.0.0.1:8029")
ENTRA_EMULATOR_INTERNAL_HOST = os.getenv(
    "ENTRA_EMULATOR_INTERNAL_HOST", "http://host.docker.internal:8029"
)
ENTRA_PUBLIC_BASE = os.getenv("NEXT_PUBLIC_ENTRA_EMULATOR_PUBLIC_BASE", "/entra")
OAUTH_REDIRECT_PATH = os.getenv("NEXT_PUBLIC_OAUTH_REDIRECT_PATH", "/auth/callback")

DIRECTORY_SERVICE_URL = os.getenv("DIRECTORY_SERVICE_URL", "")
DIRECTORY_SERVICE_AUTH_MODE = os.getenv("DIRECTORY_SERVICE_AUTH_MODE", "none")

# Shared async HTTP client (created lazily)
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(follow_redirects=False, timeout=30.0)
    return _http_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_origin(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host", request.base_url.hostname)
    proto = forwarded_proto or request.url.scheme
    return f"{proto}://{host}"


def _forward_headers(request: Request) -> dict[str, str]:
    """Pick headers to forward to upstream."""
    headers = {}
    for key in ("cookie", "content-type", "accept", "authorization", "apikey", "prefer",
                "x-client-info", "range"):
        val = request.headers.get(key)
        if val:
            headers[key] = val
    return headers


def _build_response(upstream: httpx.Response) -> Response:
    """Convert httpx response to FastAPI response, forwarding key headers."""
    excluded = {"transfer-encoding", "content-encoding", "content-length"}
    headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Reverse Proxy: /supabase/*
# ---------------------------------------------------------------------------

@router.api_route(
    "/supabase/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["proxy"],
)
async def proxy_supabase(path: str, request: Request):
    """Proxy requests to local Supabase instance."""
    qs = str(request.url.query)
    url = f"{SUPABASE_INTERNAL_URL}/{path}" + (f"?{qs}" if qs else "")
    body = await request.body()
    resp = await _get_client().request(
        method=request.method,
        url=url,
        headers=_forward_headers(request),
        content=body,
    )
    # Intercept redirects from Supabase auth callback: rewrite site_url (port 3090)
    # to the actual origin the browser is using (port 8090).
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("location", "")
        if location:
            origin = _get_origin(request)
            # Supabase uses SITE_URL for redirects — replace it with our origin
            site_url = os.getenv("SUPABASE_SITE_URL", "http://10.1.1.11:3090")
            if location.startswith(site_url):
                location = origin + location[len(site_url):]
            response = RedirectResponse(url=location, status_code=resp.status_code)
            for val in resp.headers.get_list("set-cookie"):
                response.headers.append("set-cookie", val)
            return response
    return _build_response(resp)


# ---------------------------------------------------------------------------
# Reverse Proxy: /entra/* and /common/*
# ---------------------------------------------------------------------------

@router.api_route(
    "/entra/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["proxy"],
)
async def proxy_entra(path: str, request: Request):
    """Proxy requests to Entra ID emulator."""
    qs = str(request.url.query)
    url = f"{ENTRA_INTERNAL_URL}/{path}" + (f"?{qs}" if qs else "")
    body = await request.body()
    resp = await _get_client().request(
        method=request.method,
        url=url,
        headers=_forward_headers(request),
        content=body,
    )
    return _build_response(resp)


@router.api_route(
    "/common/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["proxy"],
)
async def proxy_common(path: str, request: Request):
    """Proxy /common/* to Entra emulator (OIDC discovery etc.)."""
    qs = str(request.url.query)
    url = f"{ENTRA_INTERNAL_URL}/common/{path}" + (f"?{qs}" if qs else "")
    body = await request.body()
    resp = await _get_client().request(
        method=request.method,
        url=url,
        headers=_forward_headers(request),
        content=body,
    )
    return _build_response(resp)


# ---------------------------------------------------------------------------
# Auth: GET /api/auth/authorize
# ---------------------------------------------------------------------------

@router.get("/api/auth/authorize", tags=["auth"])
async def auth_authorize(request: Request):
    """
    Start OAuth flow. Proxies to Supabase authorize, then rewrites the
    Entra emulator redirect URL so the browser can reach it via /entra proxy.
    """
    origin = _get_origin(request)

    params = dict(request.query_params)
    params["redirect_to"] = f"{origin}{OAUTH_REDIRECT_PATH}"

    target_url = f"{SUPABASE_INTERNAL_URL}/auth/v1/authorize?{urllib.parse.urlencode(params)}"

    resp = await _get_client().get(target_url, follow_redirects=False)

    location = resp.headers.get("location")
    if not location:
        return JSONResponse({"error": "No redirect from Supabase"}, status_code=502)

    try:
        loc_url = urllib.parse.urlparse(location)
        emulator_internal = urllib.parse.urlparse(ENTRA_EMULATOR_INTERNAL_HOST)

        # If redirect points to the emulator internal host, rewrite to /entra proxy
        if loc_url.scheme == emulator_internal.scheme and loc_url.netloc == emulator_internal.netloc:
            base_path = ENTRA_PUBLIC_BASE.rstrip("/")
            new_path = f"{base_path}{loc_url.path}"
            # Rewrite redirect_uri to match GOTRUE_EXTERNAL_AZURE_REDIRECT_URI
            # so the token exchange succeeds (redirect_uri must match exactly).
            qs_params = urllib.parse.parse_qs(loc_url.query, keep_blank_values=True)
            # redirect_uri must match GOTRUE_EXTERNAL_AZURE_REDIRECT_URI exactly,
            # because Supabase uses it in the token exchange with the emulator.
            gotrue_redirect = os.getenv(
                "GOTRUE_EXTERNAL_AZURE_REDIRECT_URI",
                f"{origin}/supabase/auth/v1/callback",
            )
            qs_params["redirect_uri"] = [gotrue_redirect]
            new_query = urllib.parse.urlencode(qs_params, doseq=True)
            new_location = f"{origin}{new_path}?{new_query}"
        else:
            new_location = location

        response = RedirectResponse(url=new_location, status_code=302)
        # Forward set-cookie from Supabase (PKCE code verifier)
        for val in resp.headers.get_list("set-cookie"):
            response.headers.append("set-cookie", val)
        return response

    except Exception as e:
        return JSONResponse(
            {"error": f"Invalid redirect URL from Supabase: {e}"}, status_code=502
        )


# ---------------------------------------------------------------------------
# Auth: POST /api/auth/session
# ---------------------------------------------------------------------------

@router.post("/api/auth/session", tags=["auth"])
async def auth_session(request: Request):
    """
    Accept access_token + refresh_token, call Supabase to verify them,
    and set the auth cookie so the browser is authenticated.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not access_token or not refresh_token:
        return JSONResponse(
            {"error": "access_token and refresh_token are required"}, status_code=400
        )

    # Verify tokens with Supabase by calling GET /auth/v1/user
    verify_resp = await _get_client().get(
        f"{SUPABASE_INTERNAL_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "authorization": f"Bearer {access_token}",
        },
    )

    if verify_resp.status_code != 200:
        return JSONResponse({"error": "Invalid tokens"}, status_code=400)

    user_data = verify_resp.json()

    # Decode JWT to extract expiry (exp claim)
    expires_in = 3600
    expires_at = int(time.time()) + expires_in  # safe fallback
    try:
        token_parts = access_token.split(".")
        if len(token_parts) >= 2:
            padded = token_parts[1] + "=" * (-len(token_parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
            if "exp" in claims:
                expires_at = claims["exp"]
                expires_in = max(int(expires_at - time.time()), 0)
    except Exception:
        pass

    # Build the full session object
    session = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "expires_at": expires_at,
        "user": user_data,
    }

    # Return session in the body so the bootstrap HTML can set the cookie
    # client-side (avoids Python ↔ JS cookie format mismatches).
    # The bootstrap HTML handles base64url encoding and document.cookie setting.
    return JSONResponse({"ok": True, "session": session})


# ---------------------------------------------------------------------------
# Auth: GET /auth/callback
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/auth/callback", tags=["auth"])
async def auth_callback(request: Request):
    """
    OAuth callback handler.

    Serves the static Next.js /auth/callback page and lets the browser-side
    supabase.auth.exchangeCodeForSession() handle PKCE. This avoids re-implementing
    PKCE in Python and relies on @supabase/ssr reading the cookie verifier correctly.

    Only error redirects are handled server-side (before HTML is served).
    """
    origin = _get_origin(request)
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")

    if error:
        login_url = f"{origin}/login?error={urllib.parse.quote(error)}"
        if error_description:
            login_url += f"&error_description={urllib.parse.quote(error_description)}"
        return RedirectResponse(url=login_url, status_code=302)

    # Serve the pre-built static callback page.
    # The compiled React bundle calls exchangeCodeForSession(code) which reads
    # the PKCE verifier from the browser cookie and exchanges with GoTrue.
    for candidate in [
        _STATIC_DIR / "auth" / "callback.html",
        _STATIC_DIR / "auth" / "callback" / "index.html",
    ]:
        if candidate.is_file():
            return FileResponse(str(candidate))

    # Fallback if static files are not built yet (dev without assemble)
    return _session_bootstrap_html(origin, None)


def _session_bootstrap_html(origin: str, tokens: dict | None) -> HTMLResponse:
    """
    Serve an HTML page that sets the auth cookie client-side and redirects home.

    The cookie is set via document.cookie in the browser, using the exact same
    base64url encoding that @supabase/ssr expects. This avoids any format
    mismatches from server-side cookie setting.

    For PKCE flow (tokens from server): the full session (with user) is already
    available — set cookie directly and redirect.

    For implicit flow (tokens in hash fragment): extract tokens, POST to
    /api/auth/session to get the full session (with user), then set cookie.
    """
    home_url = f"{origin}/"
    login_url = f"{origin}/login"
    session_url = f"{origin}/api/auth/session"
    sync_profile_url = f"{origin}/api/auth/sync-profile"
    cookie_name = AUTH_COOKIE_NAME
    tokens_json = json.dumps(tokens) if tokens else "null"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Authenticating…</title>
</head>
<body>
  <p>Authenticating…</p>
  <script>
    (function() {{
      var homeUrl = {json.dumps(home_url)};
      var loginUrl = {json.dumps(login_url)};
      var sessionUrl = {json.dumps(session_url)};
      var syncProfileUrl = {json.dumps(sync_profile_url)};
      var cookieName = {json.dumps(cookie_name)};
      var tokens = {tokens_json};

      // --- Base64url encoder (matches @supabase/ssr stringToBase64URL) ---
      function toBase64URL(str) {{
        // UTF-8 encode then base64url (no padding)
        var utf8 = unescape(encodeURIComponent(str));
        var b64 = btoa(utf8);
        return b64.replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
      }}

      // --- Set the auth cookie via document.cookie ---
      function setAuthCookie(session) {{
        var json = JSON.stringify(session);
        var encoded = "base64-" + toBase64URL(json);

        // Clear any stale cookies (base + chunks)
        var expires = "expires=Thu, 01 Jan 1970 00:00:00 GMT";
        document.cookie = cookieName + "=; path=/; " + expires;
        for (var i = 0; i < 10; i++) {{
          document.cookie = cookieName + "." + i + "=; path=/; " + expires;
        }}

        // Chunk if needed (max ~3072 chars per cookie)
        var maxChunk = 3072;
        if (encoded.length <= maxChunk) {{
          document.cookie = cookieName + "=" + encoded + "; path=/; samesite=lax";
        }} else {{
          for (var idx = 0; idx * maxChunk < encoded.length; idx++) {{
            var chunk = encoded.substring(idx * maxChunk, (idx + 1) * maxChunk);
            document.cookie = cookieName + "." + idx + "=" + chunk + "; path=/; samesite=lax";
          }}
        }}

        console.log("[AUTH] Cookie set, encoded length:", encoded.length,
                    "chunked:", encoded.length > maxChunk);
      }}

      // --- Main flow ---

      // If no tokens from PKCE, check hash fragment (implicit flow)
      if (!tokens) {{
        var hash = window.location.hash.substring(1);
        if (hash) {{
          var params = new URLSearchParams(hash);
          var at = params.get("access_token");
          var rt = params.get("refresh_token");
          if (at && rt) {{
            tokens = {{ access_token: at, refresh_token: rt }};
          }}
        }}
      }}

      if (!tokens || !tokens.access_token || !tokens.refresh_token) {{
        console.error("[AUTH] No tokens available, redirecting to login");
        window.location.replace(loginUrl);
        return;
      }}

      // Check if we have a full session (PKCE gives us user, expires_at, etc.)
      if (tokens.user && tokens.expires_at) {{
        // PKCE flow: full session available — set cookie directly
        setAuthCookie(tokens);
        console.log("[AUTH] PKCE session cookie set, syncing profile...");

        // Best-effort profile sync, then redirect
        fetch(syncProfileUrl, {{ method: "POST", credentials: "include" }})
          .finally(function() {{
            console.log("[AUTH] Redirecting home");
            window.location.replace(homeUrl);
          }});
      }} else {{
        // Implicit flow: need server to verify tokens and build full session
        fetch(sessionUrl, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          credentials: "include",
          body: JSON.stringify({{
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token
          }})
        }})
          .then(function(res) {{
            if (!res.ok) throw new Error("Session exchange failed: " + res.status);
            return res.json();
          }})
          .then(function(data) {{
            if (data.session) {{
              // Server returned full session — set cookie client-side
              setAuthCookie(data.session);
            }}
            return fetch(syncProfileUrl, {{ method: "POST", credentials: "include" }});
          }})
          .then(function() {{
            window.location.replace(homeUrl);
          }})
          .catch(function(err) {{
            console.error("[AUTH] Failed:", err);
            window.location.replace(loginUrl);
          }});
      }}
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html, headers={"cache-control": "no-store"})


def _fire_and_forget_sync(origin: str, access_token: str):
    """Best-effort profile sync after login."""
    import asyncio

    async def _sync():
        try:
            await _get_client().post(
                f"{origin}/api/auth/sync-profile",
                headers={"authorization": f"Bearer {access_token}"},
            )
        except Exception:
            pass

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_sync())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auth: POST /api/auth/signout
# ---------------------------------------------------------------------------

@router.post("/api/auth/signout", tags=["auth"])
async def auth_signout(request: Request):
    """Sign out: call Supabase to revoke session, clear auth cookies."""
    # Extract access token from cookie to revoke the session
    cookie_data = _read_auth_cookie(request)
    if cookie_data:
        access_token = cookie_data.get("access_token")
        if access_token:
            await _get_client().post(
                f"{SUPABASE_INTERNAL_URL}/auth/v1/logout",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "authorization": f"Bearer {access_token}",
                },
            )

    response = JSONResponse({"ok": True})
    # Clear all possible cookie chunks
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    for i in range(5):
        response.delete_cookie(f"{AUTH_COOKIE_NAME}.{i}", path="/")
    return response


# ---------------------------------------------------------------------------
# Auth: POST /api/auth/sync-profile
# ---------------------------------------------------------------------------

@router.post("/api/auth/sync-profile", tags=["auth"])
async def auth_sync_profile(request: Request):
    """
    Sync user profile from directory service (Graph API / Entra emulator)
    into Supabase user_profiles table.
    """
    if not DIRECTORY_SERVICE_URL:
        return JSONResponse({"ok": True, "reason": "directory_not_configured"})

    # Get user from auth cookie or Authorization header
    cookie_data = _read_auth_cookie(request)
    access_token = None
    if cookie_data:
        access_token = cookie_data.get("access_token")
    if not access_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
    if not access_token:
        return JSONResponse({"ok": True, "reason": "no_token"})

    # Get user info from Supabase
    user_resp = await _get_client().get(
        f"{SUPABASE_INTERNAL_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "authorization": f"Bearer {access_token}",
        },
    )
    if user_resp.status_code != 200:
        return JSONResponse({"ok": True, "reason": "user_fetch_failed"})

    user = user_resp.json()
    user_id = user.get("id")
    email = user.get("email")
    if not email:
        return JSONResponse({"ok": True, "reason": "no_email"})

    # Fetch from directory service
    graph_url = (
        f"{DIRECTORY_SERVICE_URL}/v1.0/users/"
        f"{urllib.parse.quote(email)}?$select=id,displayName,jobTitle,department,mail"
    )
    headers = {"Accept": "application/json"}
    try:
        dir_resp = await _get_client().get(graph_url, headers=headers)
    except Exception:
        return JSONResponse({"ok": True, "reason": "directory_unavailable"})

    if dir_resp.status_code != 200:
        return JSONResponse({"ok": True, "reason": "directory_unavailable"})

    dir_user = dir_resp.json()

    # Upsert into Supabase user_profiles via PostgREST
    await _get_client().post(
        f"{SUPABASE_INTERNAL_URL}/rest/v1/user_profiles",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "prefer": "resolution=merge-duplicates",
        },
        json={
            "id": user_id,
            "job_title": dir_user.get("jobTitle"),
            "department": dir_user.get("department"),
        },
    )

    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _read_auth_cookie(request: Request) -> Optional[dict]:
    """Read and parse the Supabase auth cookie (handles chunked and base64url cookies)."""
    raw = request.cookies.get(AUTH_COOKIE_NAME)

    # Try chunked cookies if no base cookie
    if not raw:
        chunks = []
        for i in range(10):
            chunk = request.cookies.get(f"{AUTH_COOKIE_NAME}.{i}")
            if chunk is None:
                break
            chunks.append(chunk)
        if chunks:
            raw = "".join(chunks)

    if not raw:
        return None

    return _decode_cookie_value(raw)


def _decode_cookie_value(raw: str) -> Optional[dict]:
    """Decode a cookie value that may be base64url-encoded, URL-encoded, or plain JSON."""
    # base64url format (@supabase/ssr v0.8+ default)
    if raw.startswith("base64-"):
        try:
            b64 = raw[7:]
            # Re-add padding if stripped (Python's b64decode requires it)
            b64 += "=" * (-len(b64) % 4)
            decoded = base64.urlsafe_b64decode(b64).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            pass

    # Direct JSON
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    # URL-encoded JSON (legacy)
    try:
        return json.loads(urllib.parse.unquote(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    return None
