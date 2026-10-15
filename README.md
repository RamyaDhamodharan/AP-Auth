# AP Auth Service

FastAPI starter for authentication, refresh sessions, RBAC and admin user management, following the GenWorx AP Assistant LLD.

## Windows local run
1. Install Python 3.11+ and `uv`.
2. In this folder: `uv sync --extra dev`
3. Copy `.env.example` to `.env` and configure `DATABASE_URL` for the shared local PostgreSQL database.
4. Run: `uv run uvicorn src.main:app --reload --port 8001`
5. Open `http://127.0.0.1:8001/docs` or `http://127.0.0.1:8001/health`.

Only health check is implemented. Login, JWT cookies, Argon2, lockout, audit events and admin routes are not implemented yet.
