# Piano Correzione Auth (Riprendibile)

> **Stato: COMPLETATO** (2026-02-13)
> Tutti gli step 1-3 sono stati implementati e verificati.
> Lo step 4 (hardening opzionale) resta disponibile per il futuro.

---

## STEP 1 - LDAP parametrico + restart + verifica ✅

Obiettivo: rendere `ldap-emulator` dipendente solo dal suo `.env` (niente fallback server-specific in `docker-compose.yml`).

Azioni completate:
- `docker-compose.yml`: porte parametrizzate via `${EMULATOR_PORT:-8029}`, aggiunto `env_file: .env`
- `.env.example` creato con valori localhost generici
- `config.py`: aggiunti `ALLOW_DYNAMIC_REDIRECT_URI` e `DEFAULT_APP_REDIRECT_URIS`
- `app_service.py`: redirect URI di default letti da config
- Documentazione aggiornata (README, user-manual, developer-manual, user-management)

Verifica superata:
- `docker compose config` OK
- `curl http://localhost:8029/health` → 200
- issuer coerente con `.env`

---

## STEP 2 - /auth/callback canonico centralizzato + verifica ✅

Obiettivo: mantenere `/auth/callback` canonico, usarlo da un solo punto (`NEXT_PUBLIC_OAUTH_REDIRECT_PATH` + helper).

Azioni completate:
- `lib/auth/provider.ts`: helper centralizzato `getOAuthRedirectPath()`
- `AuthContext.tsx`, `login/page.tsx`, `auth/callback/route.ts`: usano tutti il helper
- `api/auth/authorize/route.ts`: proxy con rewrite dinamico origin-aware
- Nessun hardcode residuo di `/auth/callback` fuori dal helper

Verifica superata:
- Login flow emulator funzionante
- Redirect coerente verso path canonico
- Sessione impostata correttamente

---

## STEP 3 - SITE_URL + ADDITIONAL_REDIRECT_URLS + verifica ✅

Obiettivo: allineare `supabase-project/.env` ai due scenari (server/local) senza mismatch callback.

Azioni completate:
- `supabase-project/.env.example` creato con template completo localhost
- `elysia-frontend/config/env/` profili example per local e server-vpn
- `verify-auth-config.sh` con path relativi portabili (non più `/opt/athena/`)
- WebSocket porta parametrizzata via `NEXT_PUBLIC_ELYSIA_WS_PORT`
- `supabase-project` inizializzato come repo git con `.gitignore`

Verifica superata:
- `verify-auth-config.sh` → "Configuration checks completed"
- Profili local e server-vpn coerenti

---

## STEP 4 (opzionale) - hardening + validazione finale

Obiettivo: robustezza e trasferibilita.

Azioni future possibili:
- Check di startup/validazione env (fail-fast se variabili mancanti)
- Sync redirect list se `ALLOW_DYNAMIC_REDIRECT_URI=false`
- Smoke test automatizzato login/logout/session refresh

Criterio OK:
- stessi binari/codice
- cambia solo `.env`
