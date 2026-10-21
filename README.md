# AP Auth Service

FastAPI starter for authentication, refresh sessions, RBAC and admin user management, following the GenWorx AP Assistant LLD.

## Windows local run
1. Install Python 3.11+ and `uv`.
2. In this folder: `uv sync --extra dev`
3. Copy `.env.example` to `.env` and configure `DATABASE_URL` for the shared local PostgreSQL database.
4. Run: `uv run uvicorn src.main:app --reload --port 8001`
5. Open `http://127.0.0.1:8001/docs` or `http://127.0.0.1:8001/health`.

Access tokens are short-lived and returned to the frontend for in-memory use only. Refresh tokens are opaque, stored server-side as SHA-256 hashes, and delivered only in a Secure, HttpOnly cookie. Configure `CORS_ALLOWED_ORIGINS` for the exact browser origins. The cookie is host-only by default, scoped to `/api/auth`, and uses `SameSite=Lax`; set `REFRESH_COOKIE_SAMESITE=none` only for an HTTPS deployment where the frontend and Auth are cross-site. Set `REFRESH_COOKIE_DOMAIN` only when deliberately sharing the cookie across trusted subdomains. Secure cookies are always enabled.

Apply Auth migrations with `uv run alembic upgrade head`. This adds the refresh session table only if it is not already present; the migration downgrade intentionally preserves the session table and its data.
