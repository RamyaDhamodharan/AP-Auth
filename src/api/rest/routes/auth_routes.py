from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.core.config_core import get_settings
from src.core.security_core import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from src.db.session_db import get_db
from src.models.refresh_session_models import RefreshSession
from src.models.user_models import User
from src.schemas.auth_schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
)
from src.services.auth_services import (
    check_password,
    get_user_by_email,
    hash_new_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _csrf_check(request: Request) -> None:
    settings = get_settings()
    allowed_origins = {
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    }
    origin = request.headers.get("origin")
    if origin not in allowed_origins or request.headers.get("x-csrf-protection") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=True,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _unauthorized(detail: str = "Invalid refresh session") -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail},
    )
    _clear_refresh_cookie(response)
    return response


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    email = str(payload.email).lower()

    existing_user = get_user_by_email(db, email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        name=payload.full_name.strip(),
        email=email,
        role="associate",
        password_hash=hash_new_password(payload.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except Exception as e:
        db.rollback()
        print("REGISTRATION ERROR:", repr(e))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register user",
        ) from e

    return MessageResponse(message="Registration successful")


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    email = str(payload.email).lower()

    user = get_user_by_email(db, email)

    if not user or not check_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    settings = get_settings()
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token()
    now = datetime.now(UTC)
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            created_by=user.id,
            updated_by=user.id,
        )
    )
    user.last_login_at = now
    db.add(user)
    db.commit()
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=None)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None, alias=get_settings().refresh_cookie_name
    ),
) -> TokenResponse | JSONResponse:
    _csrf_check(request)
    if not refresh_token:
        return _unauthorized()

    now = datetime.now(UTC)
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
        .first()
    )
    if session is None:
        return _unauthorized()
    if session.is_revoked:
        db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == session.user_id,
                RefreshSession.is_revoked.is_(False),
            )
            .values(
                is_revoked=True,
                revoked_at=now,
                updated_at=now,
                updated_by=session.user_id,
            )
        )
        db.commit()
        return _unauthorized("Refresh token reuse detected")
    if session.expires_at <= now:
        session.is_revoked = True
        session.revoked_at = now
        session.updated_at = now
        session.updated_by = session.user_id
        db.commit()
        return _unauthorized("Refresh session expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        session.is_revoked = True
        session.revoked_at = now
        session.updated_at = now
        session.updated_by = session.user_id
        db.commit()
        return _unauthorized("Account is unavailable")

    settings = get_settings()
    rotated_token = create_refresh_token()
    session.is_revoked = True
    session.revoked_at = now
    session.updated_at = now
    session.updated_by = user.id
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(rotated_token),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    _set_refresh_cookie(response, rotated_token)
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
        must_change_password=user.must_change_password,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None, alias=get_settings().refresh_cookie_name
    ),
) -> Response:
    _csrf_check(request)
    if refresh_token:
        now = datetime.now(UTC)
        session = (
            db.query(RefreshSession)
            .filter(RefreshSession.token_hash == hash_refresh_token(refresh_token))
            .with_for_update()
            .first()
        )
        if session is not None and not session.is_revoked:
            session.is_revoked = True
            session.revoked_at = now
            session.updated_at = now
            session.updated_by = session.user_id
            db.commit()
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
