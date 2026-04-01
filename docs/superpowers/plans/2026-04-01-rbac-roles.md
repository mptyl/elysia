# RBAC Roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add many-to-many role-based authorization (RBAC) tables to Supabase, remove the legacy `app_role` column, display roles read-only in the frontend Profile page, and pass roles to the Elysia backend during user init.

**Architecture:** New `roles` catalog + `user_roles` junction table in Supabase with RLS. A trigger auto-assigns the `USER` role on profile creation. The frontend fetches roles via the `useUserProfile` hook and sends them to Elysia's `/init/user` endpoint. The backend stores roles in-memory on the `UserManager`.

**Tech Stack:** PostgreSQL (Supabase), TypeScript/React (Next.js 14), Python (FastAPI/Pydantic)

**Spec:** `plans/gestione_ruoli.md`

---

### Task 1: Add `roles` and `user_roles` tables to Supabase schema

**Files:**
- Modify: `supabase-project/volumes/db/athena_schema.sql` (append after line 157)

- [ ] **Step 1: Add roles table, user_roles junction table, auto-assign trigger, and RLS to the schema file**

Append the following SQL block at the end of `supabase-project/volumes/db/athena_schema.sql` (after the role_standard_instructions seed):

```sql
-- ============================================================
-- 6. Roles (RBAC catalog)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'roles'
          AND policyname = 'roles_select_authenticated'
    ) THEN
        CREATE POLICY roles_select_authenticated
            ON public.roles
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

GRANT SELECT ON public.roles TO authenticated;
GRANT ALL ON public.roles TO service_role;
GRANT ALL ON public.roles TO postgres;

-- Seed roles
INSERT INTO public.roles (name, description) VALUES
    ('ADMIN',   'Amministratore di sistema con accesso completo'),
    ('THOTH',   'Accesso alle funzionalita ThothAI'),
    ('NORME',   'Accesso ai contenuti normativi'),
    ('GRAPHIC', 'Accesso agli strumenti di grafica'),
    ('USER',    'Ruolo base assegnato a tutti gli utenti')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 7. User Roles (many-to-many junction: user_profiles <-> roles)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON public.user_roles(user_id);

ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_roles'
          AND policyname = 'user_roles_select_own'
    ) THEN
        CREATE POLICY user_roles_select_own
            ON public.user_roles
            FOR SELECT TO authenticated USING (auth.uid() = user_id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_roles'
          AND policyname = 'user_roles_service_role_all'
    ) THEN
        CREATE POLICY user_roles_service_role_all
            ON public.user_roles
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
GRANT ALL ON public.user_roles TO postgres;

-- ============================================================
-- 8. Auto-assign USER role on profile creation
-- ============================================================

CREATE OR REPLACE FUNCTION public.assign_default_role()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_roles (user_id, role_id)
    SELECT NEW.id, r.id FROM public.roles r WHERE r.name = 'USER'
    ON CONFLICT (user_id, role_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_user_profile_created_assign_role ON public.user_profiles;
CREATE TRIGGER on_user_profile_created_assign_role
    AFTER INSERT ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.assign_default_role();

-- ============================================================
-- 9. Seed: USER role for all existing profiles, ADMIN for initial admins
-- ============================================================

INSERT INTO public.user_roles (user_id, role_id)
SELECT up.id, r.id
FROM public.user_profiles up
CROSS JOIN public.roles r
WHERE r.name = 'USER'
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO public.user_roles (user_id, role_id)
SELECT up.id, r.id
FROM auth.users au
JOIN public.user_profiles up ON up.id = au.id
CROSS JOIN public.roles r
WHERE r.name = 'ADMIN'
  AND au.email IN (
    'leonardo.porcacchia@uni.com',
    'simone.mezzabotta@uni.com',
    'marco.pancotti@ext_uni.com',
    'sofia.zanrosso@uni.com',
    'lisa.inversini@uni.com',
    'domenico.falvella@uni.com',
    'paolo.sanna@uni.com'
  )
ON CONFLICT (user_id, role_id) DO NOTHING;
```

- [ ] **Step 2: Verify the appended SQL is syntactically correct**

Run: `cd /opt/athena/supabase-project && docker compose exec db psql -U supabase_admin -d postgres -f /dev/stdin <<< "SELECT 1;" `
Expected: Connection works. (Actual schema application happens on restart/migration.)

- [ ] **Step 3: Commit**

```bash
git add supabase-project/volumes/db/athena_schema.sql
git commit -m "feat(supabase): add roles and user_roles tables with RLS, trigger, and seed data"
```

---

### Task 2: Remove `app_role` column from Supabase schema and update `handle_new_user` trigger

**Files:**
- Modify: `supabase-project/volumes/db/athena_schema.sql:30-50` (user_profiles table)
- Modify: `supabase-project/volumes/db/athena_schema.sql:97-108` (handle_new_user function)

- [ ] **Step 1: Remove `app_role` from `user_profiles` CREATE TABLE**

In `supabase-project/volumes/db/athena_schema.sql`, change line 33 from:

```sql
    app_role text NOT NULL DEFAULT 'user',
```

to nothing (delete the line entirely).

- [ ] **Step 2: Update `handle_new_user()` function to remove `app_role`**

In the same file, replace lines 97-108:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.user_profiles (id, display_name, app_role)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'Display Name', NEW.raw_user_meta_data->>'full_name', ''),
        'user'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

with:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.user_profiles (id, display_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'Display Name', NEW.raw_user_meta_data->>'full_name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

- [ ] **Step 3: Commit**

```bash
git add supabase-project/volumes/db/athena_schema.sql
git commit -m "feat(supabase): remove app_role column from user_profiles, update handle_new_user trigger"
```

---

### Task 3: Remove `app_role` from frontend profile schema copy

**Files:**
- Modify: `elysia-frontend/scripts/auth-config/profile-schema.sql:48`

- [ ] **Step 1: Remove `app_role` line from the frontend schema copy**

In `elysia-frontend/scripts/auth-config/profile-schema.sql`, delete line 48:

```sql
    app_role text not null default 'user',
```

- [ ] **Step 2: Commit**

```bash
git add elysia-frontend/scripts/auth-config/profile-schema.sql
git commit -m "feat(frontend): remove app_role from profile-schema.sql"
```

---

### Task 4: Update TypeScript types — remove `app_role`, add `roles`

**Files:**
- Modify: `elysia-frontend/app/types/profile-types.ts:27-42`

- [ ] **Step 1: Replace `app_role` with `roles` in UserProfile interface**

In `elysia-frontend/app/types/profile-types.ts`, replace the `UserProfile` interface (lines 27-42):

```ts
export interface UserProfile {
    id: string;
    display_name: string | null;
    department_id: string | null;
    job_title: string | null;
    department: string | null;
    app_role: string;
    response_detail_level: ResponseDetailLevel;
    communication_tone: CommunicationTone;
    preferred_language: PreferredLanguage;
    response_focus: ResponseFocus;
    custom_instructions: string;
    custom_instructions_mode: CustomInstructionsMode;
    created_at?: string;
    updated_at?: string;
}
```

with:

```ts
export interface UserProfile {
    id: string;
    display_name: string | null;
    department_id: string | null;
    job_title: string | null;
    department: string | null;
    roles: string[];
    response_detail_level: ResponseDetailLevel;
    communication_tone: CommunicationTone;
    preferred_language: PreferredLanguage;
    response_focus: ResponseFocus;
    custom_instructions: string;
    custom_instructions_mode: CustomInstructionsMode;
    created_at?: string;
    updated_at?: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add elysia-frontend/app/types/profile-types.ts
git commit -m "feat(frontend): replace app_role with roles: string[] in UserProfile type"
```

---

### Task 5: Update `useUserProfile` hook — remove `app_role`, fetch roles from `user_roles`

**Files:**
- Modify: `elysia-frontend/hooks/useUserProfile.ts`

- [ ] **Step 1: Remove `app_role` from the default profile object**

In `elysia-frontend/hooks/useUserProfile.ts`, replace the `newProfile` object (lines 47-57):

```ts
                const newProfile = {
                    id: userId,
                    department_id: null,
                    app_role: "user",
                    response_detail_level: "balanced",
                    communication_tone: "professional",
                    preferred_language: "it",
                    response_focus: "technical",
                    custom_instructions: "",
                    custom_instructions_mode: "append",
                };
```

with:

```ts
                const newProfile = {
                    id: userId,
                    department_id: null,
                    response_detail_level: "balanced",
                    communication_tone: "professional",
                    preferred_language: "it",
                    response_focus: "technical",
                    custom_instructions: "",
                    custom_instructions_mode: "append",
                };
```

- [ ] **Step 2: Add roles fetch after department fetch**

In the same file, after the department fetch block (after line 108, `dept = (deptRow as Department | null) ?? null;`), add:

```ts
            // Fetch user roles from the junction table
            const { data: rolesData, error: rolesError } = await supabase
                .from("user_roles")
                .select("roles(name)")
                .eq("user_id", resolvedProfile.id);

            if (rolesError) {
                throw rolesError;
            }

            const roles: string[] = (rolesData ?? [])
                .map((r: { roles: { name: string } | null }) => r.roles?.name)
                .filter((name): name is string => !!name);
```

- [ ] **Step 3: Include `roles` in the returned profile object**

Replace the `setProfile` call (lines 110-113):

```ts
            setProfile({
                ...resolvedProfile,
                departments: dept,
            } as UserProfileWithDepartment);
```

with:

```ts
            setProfile({
                ...resolvedProfile,
                roles,
                departments: dept,
            } as UserProfileWithDepartment);
```

- [ ] **Step 4: Commit**

```bash
git add elysia-frontend/hooks/useUserProfile.ts
git commit -m "feat(frontend): fetch roles from user_roles table in useUserProfile hook"
```

---

### Task 6: Add i18n translations for roles section

**Files:**
- Modify: `elysia-frontend/messages/it.json`
- Modify: `elysia-frontend/messages/en.json`

- [ ] **Step 1: Add Italian translations**

In `elysia-frontend/messages/it.json`, inside the `"profile"` object (after line 137, `"saved": "Profilo salvato!"`), add:

```json
    "roles": "Ruoli",
    "noRoles": "Nessun ruolo assegnato"
```

(Don't forget to add a comma after `"saved": "Profilo salvato!"`)

- [ ] **Step 2: Add English translations**

In `elysia-frontend/messages/en.json`, inside the `"profile"` object (after `"saved": "Profile saved!"`), add:

```json
    "roles": "Roles",
    "noRoles": "No roles assigned"
```

(Don't forget to add a comma after `"saved": "Profile saved!"`)

- [ ] **Step 3: Commit**

```bash
git add elysia-frontend/messages/it.json elysia-frontend/messages/en.json
git commit -m "feat(frontend): add i18n translations for roles section in profile page"
```

---

### Task 7: Add roles display to ProfilePage

**Files:**
- Modify: `elysia-frontend/app/pages/ProfilePage.tsx`

- [ ] **Step 1: Add read-only roles section after the job title/department row**

In `elysia-frontend/app/pages/ProfilePage.tsx`, after the department/job title `</div>` (after line 188, the closing `</div>` of the flex gap-4 container), and before the separator `<div className="h-px w-full bg-border" />` on line 190, add:

```tsx
                        {/* Roles (read-only) */}
                        <div className="flex flex-col gap-2">
                            <Label className="text-sm font-semibold text-secondary uppercase tracking-wider">
                                {t('roles')}
                            </Label>
                            <div className="flex flex-wrap gap-2">
                                {profile?.roles && profile.roles.length > 0 ? (
                                    profile.roles.map((role) => (
                                        <span
                                            key={role}
                                            className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium border border-primary/20"
                                        >
                                            {role}
                                        </span>
                                    ))
                                ) : (
                                    <span className="italic text-secondary/50 text-sm">
                                        {t('noRoles')}
                                    </span>
                                )}
                            </div>
                        </div>
```

- [ ] **Step 2: Commit**

```bash
git add elysia-frontend/app/pages/ProfilePage.tsx
git commit -m "feat(frontend): display user roles as read-only badges in profile page"
```

---

### Task 8: Pass roles from frontend to backend in init call

**Files:**
- Modify: `elysia-frontend/app/api/initializeUser.ts`
- Modify: `elysia-frontend/hooks/useUserProfile.ts` (or wherever `initializeUser` is called)

- [ ] **Step 1: Update `initializeUser` to accept and send roles**

In `elysia-frontend/app/api/initializeUser.ts`, replace the function signature and fetch call (lines 4-14):

```ts
export async function initializeUser(
  user_id: string
): Promise<UserInitPayload> {
  const startTime = performance.now();
  try {
    const response = await fetch(`${host}/init/user/${user_id}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
```

with:

```ts
export async function initializeUser(
  user_id: string,
  roles?: string[]
): Promise<UserInitPayload> {
  const startTime = performance.now();
  try {
    const response = await fetch(`${host}/init/user/${user_id}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ roles: roles ?? [] }),
    });
```

- [ ] **Step 2: Commit**

```bash
git add elysia-frontend/app/api/initializeUser.ts
git commit -m "feat(frontend): pass roles array in initializeUser POST body"
```

---

### Task 9: Backend — accept roles in `/init/user` endpoint

**Files:**
- Modify: `elysia/elysia/api/api_types.py`
- Modify: `elysia/elysia/api/routes/init.py:51-54`
- Modify: `elysia/elysia/api/services/user.py:170-171`
- Test: `elysia/tests/no_reqs/api/test_init_nr.py`

- [ ] **Step 1: Write the failing test**

Add the following test to `elysia/tests/no_reqs/api/test_init_nr.py`, inside the `TestTree` class, after the existing `test_tree` method:

```python
    @pytest.mark.asyncio
    async def test_initialise_user_with_roles(self):
        user_manager = get_user_manager()
        user_id = "test_user_roles"

        from elysia.api.api_types import InitialiseUserData

        out = await initialise_user(
            user_id,
            InitialiseUserData(roles=["USER", "ADMIN"]),
            user_manager,
        )

        response = read_response(out)
        assert response["error"] == ""
        assert response["user_exists"] is False

        # Verify roles are stored in user manager
        assert user_manager.users[user_id]["roles"] == ["USER", "ADMIN"]

    @pytest.mark.asyncio
    async def test_initialise_user_without_roles(self):
        user_manager = get_user_manager()
        user_id = "test_user_no_roles"

        out = await initialise_user(
            user_id,
            None,
            user_manager,
        )

        response = read_response(out)
        assert response["error"] == ""

        # Without roles, defaults to empty list
        assert user_manager.users[user_id]["roles"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/athena/elysia && source .venv/bin/activate && pytest tests/no_reqs/api/test_init_nr.py::TestTree::test_initialise_user_with_roles tests/no_reqs/api/test_init_nr.py::TestTree::test_initialise_user_without_roles -v`
Expected: FAIL — `InitialiseUserData` does not exist, `initialise_user` does not accept data parameter.

- [ ] **Step 3: Add `InitialiseUserData` Pydantic model**

In `elysia/elysia/api/api_types.py`, after the `InitialiseTreeData` class (after line 27), add:

```python
class InitialiseUserData(BaseModel):
    roles: list[str] = []
```

- [ ] **Step 4: Update `/init/user` endpoint to accept optional body with roles**

In `elysia/elysia/api/routes/init.py`, add the import at line 3 (after `from cryptography.fernet import InvalidToken`):

```python
from elysia.api.api_types import InitialiseTreeData, InitialiseUserData
```

And update line 3's existing import to remove `InitialiseTreeData` from the standalone import (since it's now combined).

Replace the `initialise_user` function signature (lines 51-54):

```python
@router.post("/user/{user_id}")
async def initialise_user(
    user_id: str, user_manager: UserManager = Depends(get_user_manager)
):
```

with:

```python
@router.post("/user/{user_id}")
async def initialise_user(
    user_id: str,
    data: InitialiseUserData | None = None,
    user_manager: UserManager = Depends(get_user_manager),
):
```

Then, inside the function body, after `user_exists = user_manager.user_exists(user_id)` (after line 69), add:

```python
        roles = data.roles if data else []
```

And after the user creation block completes (after `user = await user_manager.get_user_local(user_id)` on line 107), add:

```python
        user_manager.users[user_id]["roles"] = roles
```

- [ ] **Step 5: Update `add_user_local` to initialize roles key**

In `elysia/elysia/api/services/user.py`, inside the `add_user_local` method, after line 206 (`self.users[user_id]["preferred_language"] = "it"`), still inside the `if user_id not in self.users:` block, add at the same indentation level as the `preferred_language` assignment:

```python
            self.users[user_id]["roles"] = []
```

(This goes inside the `if user_id not in self.users:` block, at the very end, before the method returns.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /opt/athena/elysia && source .venv/bin/activate && pytest tests/no_reqs/api/test_init_nr.py -v`
Expected: All tests PASS, including the two new role tests.

- [ ] **Step 7: Commit**

```bash
git add elysia/elysia/api/api_types.py elysia/elysia/api/routes/init.py elysia/elysia/api/services/user.py tests/no_reqs/api/test_init_nr.py
git commit -m "feat(backend): accept and store user roles in /init/user endpoint"
```

---

### Task 10: Run full test suite and verify nothing is broken

**Files:** (none modified)

- [ ] **Step 1: Run all no-reqs tests**

Run: `cd /opt/athena/elysia && source .venv/bin/activate && pytest --ignore=tests/requires_env -v`
Expected: All tests PASS.

- [ ] **Step 2: Verify frontend builds without type errors**

Run: `cd /opt/athena/elysia-frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Commit any fixes if needed, then tag completion**

If all tests pass, no commit needed. If fixes were required, commit them with:

```bash
git commit -m "fix: resolve issues found during RBAC full test run"
```
