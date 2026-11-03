from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import RefreshToken, User
from src.schemas.accounts import (
    AccessTokenResponse,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenPairResponse,
    UserRegisterResponse,
)
from src.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

router = APIRouter(prefix="/api/v1/accounts", tags=["Auth"])


@router.post(
    "/login/",
    response_model=TokenPairResponse,
    summary="Log in and get a pair of JWT tokens",
    description=(
        "Checks the email and password of an activated account and returns "
        "an access token (short-lived, 15 minutes) and a refresh token "
        "(7 days). Send the access token in the header "
        "`Authorization: Bearer <access_token>`."
    ),
    responses={
        401: {"description": "Invalid email or password"},
        403: {"description": "The account is not activated"},
    },
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))

    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    access_token = create_access_token(user.id)
    refresh_token, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token=refresh_token, expires_at=expires_at))
    db.commit()

    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh/",
    response_model=AccessTokenResponse,
    summary="Get a new access token",
    description=(
        "Exchanges a valid refresh token for a new access token. "
        "The refresh token must not be expired or revoked (logged out)."
    ),
    responses={401: {"description": "Invalid, expired or revoked refresh token"}},
)
def refresh_access_token(data: RefreshRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )

    try:
        payload = decode_token(data.refresh_token, "refresh")
    except ValueError:
        raise invalid

    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    if stored is None:
        raise invalid

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise invalid

    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.post(
    "/logout/",
    response_model=MessageResponse,
    summary="Log out",
    description=(
        "Deletes the refresh token from the database, so it can no longer "
        "be used to get new access tokens."
    ),
    responses={401: {"description": "Invalid refresh token"}},
)
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    db.delete(stored)
    db.commit()
    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/me/",
    response_model=UserRegisterResponse,
    summary="Get the current user",
    description="Returns the user that owns the access token. Requires authorization.",
    responses={401: {"description": "Missing, invalid or expired access token"}},
)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user