from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import RefreshToken, User
from src.schemas.accounts import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
)
from src.security import hash_password, verify_password
from src.services.email import send_password_reset_email
from src.services.tokens import build_password_reset_token, is_expired

router = APIRouter(prefix="/api/v1/accounts", tags=["Passwords"])


def _revoke_refresh_tokens(db: Session, user_id: int) -> None:
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


@router.post(
    "/change-password/",
    response_model=MessageResponse,
    summary="Change the password",
    description=(
        "Changes the password of the current user. Requires the old password. "
        "All refresh tokens are revoked, so the user has to log in again "
        "on every device."
    ),
    responses={
        400: {"description": "The old password is incorrect"},
        401: {"description": "Missing or invalid access token"},
        422: {"description": "The new password is too weak"},
    },
)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The old password is incorrect.",
        )

    current_user.hashed_password = hash_password(data.new_password)
    _revoke_refresh_tokens(db, current_user.id)
    db.commit()

    return MessageResponse(message="Password changed successfully.")


@router.post(
    "/forgot-password/",
    response_model=MessageResponse,
    summary="Request a password reset",
    description=(
        "Sends a password reset token (valid for 1 hour) to the email if it "
        "belongs to an active account. The response is always the same, so "
        "it does not reveal whether the email is registered."
    ),
)
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is not None and user.is_active:
        if user.password_reset_token is not None:
            db.delete(user.password_reset_token)
            db.flush()

        new_token = build_password_reset_token(user.id)
        db.add(new_token)
        db.commit()

        background_tasks.add_task(send_password_reset_email, email, new_token.token)

    return MessageResponse(
        message="If your account exists and is active, "
        "a password reset token has been sent."
    )


@router.post(
    "/reset-password/",
    response_model=MessageResponse,
    summary="Set a new password with a reset token",
    description=(
        "Sets a new password using the token received by email. "
        "The old password is not required. The token is deleted after use "
        "and all refresh tokens of the user are revoked."
    ),
    responses={
        400: {"description": "Invalid or expired reset token"},
        422: {"description": "The new password is too weak"},
    },
)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    token = user.password_reset_token if user else None

    if (
        user is None
        or not user.is_active
        or token is None
        or token.token != data.token
        or is_expired(token.expires_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    user.hashed_password = hash_password(data.new_password)
    db.delete(token)
    _revoke_refresh_tokens(db, user.id)
    db.commit()

    return MessageResponse(message="Password has been reset successfully.")
