import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.rest.app import app
from src.api.rest.routes import auth_routes
from src.core.config_core import get_settings
from src.db.session_db import get_db
from src.models.refresh_session_models import RefreshSession


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app, base_url="https://localhost")


def _set_db(db):
    app.dependency_overrides[get_db] = lambda: db


def _clear_db():
    app.dependency_overrides.pop(get_db, None)


def _csrf_headers():
    return {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}


def _refresh_headers():
    return {
        **_csrf_headers(),
        "Cookie": f"{get_settings().refresh_cookie_name}=presented-refresh-token",
    }


def _session(user_id, *, expires_at=None, is_revoked=False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=hashlib.sha256(b"presented-refresh-token").hexdigest(),
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=1),
        is_revoked=is_revoked,
        revoked_at=None,
        updated_at=None,
        updated_by=None,
    )


def test_login_sets_hashed_refresh_cookie_and_returns_only_access_token(
    client, monkeypatch
):
    user = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        password_hash="password-hash",
        must_change_password=False,
        last_login_at=None,
    )
    db = MagicMock()
    _set_db(db)
    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda *_args: user)
    monkeypatch.setattr(auth_routes, "check_password", lambda *_args: True)
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **_kwargs: "access")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-secret")

    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password"},
        )
    finally:
        _clear_db()

    saved_session = next(
        item
        for item in (call.args[0] for call in db.add.call_args_list)
        if isinstance(item, RefreshSession)
    )
    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access",
        "token_type": "bearer",
        "expires_in": 300,
        "must_change_password": False,
    }
    assert "refresh_token" not in response.json()
    assert response.cookies[get_settings().refresh_cookie_name] == "refresh-secret"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "secure" in response.headers["set-cookie"].lower()
    assert "path=/api/auth" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert saved_session.token_hash == hashlib.sha256(b"refresh-secret").hexdigest()
    assert saved_session.token_hash != "refresh-secret"


def test_refresh_rotates_token_and_rejects_reuse(client, monkeypatch):
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, is_active=True, must_change_password=False)
    session = _session(user_id)
    db = MagicMock()
    locked_query = (
        db.query.return_value.filter.return_value.with_for_update.return_value
    )
    locked_query.first.return_value = session
    db.get.return_value = user
    _set_db(db)
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "rotated-secret")
    monkeypatch.setattr(
        auth_routes, "create_access_token", lambda **_kwargs: "new-access"
    )

    try:
        response = client.post(
            "/api/auth/refresh",
            headers=_refresh_headers(),
        )
    finally:
        _clear_db()

    saved_session = next(
        item
        for item in (call.args[0] for call in db.add.call_args_list)
        if isinstance(item, RefreshSession)
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"
    assert "refresh_token" not in response.json()
    assert response.cookies[get_settings().refresh_cookie_name] == "rotated-secret"
    assert session.is_revoked is True
    assert saved_session.token_hash == hashlib.sha256(b"rotated-secret").hexdigest()


def test_expired_refresh_is_revoked_and_cookie_cleared(client):
    session = _session(
        uuid.uuid4(), expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    db = MagicMock()
    locked_query = (
        db.query.return_value.filter.return_value.with_for_update.return_value
    )
    locked_query.first.return_value = session
    _set_db(db)

    try:
        response = client.post(
            "/api/auth/refresh",
            headers=_refresh_headers(),
        )
    finally:
        _clear_db()

    assert response.status_code == 401
    assert session.is_revoked is True
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_revoked_refresh_reuse_revokes_other_sessions(client):
    session = _session(uuid.uuid4(), is_revoked=True)
    db = MagicMock()
    locked_query = (
        db.query.return_value.filter.return_value.with_for_update.return_value
    )
    locked_query.first.return_value = session
    _set_db(db)

    try:
        response = client.post(
            "/api/auth/refresh",
            headers=_refresh_headers(),
        )
    finally:
        _clear_db()

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token reuse detected"
    db.execute.assert_called_once()
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_logout_revokes_session_and_clears_cookie(client):
    session = _session(uuid.uuid4())
    db = MagicMock()
    locked_query = (
        db.query.return_value.filter.return_value.with_for_update.return_value
    )
    locked_query.first.return_value = session
    _set_db(db)

    try:
        response = client.post(
            "/api/auth/logout",
            headers=_refresh_headers(),
        )
    finally:
        _clear_db()

    assert response.status_code == 204
    assert session.is_revoked is True
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_cookie_refresh_requires_origin_and_csrf_header(client):
    db = MagicMock()
    _set_db(db)

    try:
        response = client.post("/api/auth/refresh")
    finally:
        _clear_db()

    assert response.status_code == 403
    db.query.assert_not_called()


def test_cors_allows_credentials_and_csrf_header_for_frontend_origin(client):
    response = client.options(
        "/api/auth/refresh",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-protection",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert (
        "x-csrf-protection" in response.headers["access-control-allow-headers"].lower()
    )
