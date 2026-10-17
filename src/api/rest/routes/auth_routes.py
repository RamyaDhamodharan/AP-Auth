from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security_core import create_access_token
from src.db.session_db import get_db
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

    access_token = create_access_token(
        subject=str(user.id),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,
        must_change_password=user.must_change_password,
    )
