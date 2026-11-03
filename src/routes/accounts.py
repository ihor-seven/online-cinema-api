from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, UserGroup, UserGroupEnum
from src.schemas.accounts import (
    ActivationRequest,
    MessageResponse,
    ResendActivationRequest,
    UserRegisterRequest,
    UserRegisterResponse,
)
from src.security import hash_password
from src.services.email import send_activation_email
from src.services.tokens import build_activation_token, is_expired

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


@router.post(
    "/register/",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new inactive account in the USER group, generates an "
        "activation token valid for 24 hours and sends it to the user's email. "
        "The password must contain at least 8 characters, an uppercase "
        "letter, a lowercase letter, a digit and a special character."
    ),
    responses={
        409: {"description": "A user with this email already exists"},
        422: {"description": "Invalid email or weak password"},
    },
)
def register_user(
    data: UserRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {email} already exists.",
        )

    group = db.scalar(select(UserGroup).where(UserGroup.name == UserGroupEnum.USER))
    if group is None:
        group = UserGroup(name=UserGroupEnum.USER)
        db.add(group)
        db.flush()

    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        group_id=group.id,
    )
    db.add(user)
    db.flush()

    activation_token = build_activation_token(user.id)
    db.add(activation_token)
    db.commit()
    db.refresh(user)

    background_tasks.add_task(send_activation_email, email, activation_token.token)

    return user


@router.post(
    "/activate/",
    response_model=MessageResponse,
    summary="Activate an account",
    description=(
        "Activates the account using the token received by email. "
        "The token is valid for 24 hours and is deleted after use."
    ),
    responses={
        400: {
            "description": "Invalid or expired token, or the account is "
            "already active"
        },
    },
)
def activate_account(data: ActivationRequest, db: Session = Depends(get_db)):
    email = data.email.lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is not None and user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active.",
        )

    token = user.activation_token if user else None
    if token is None or token.token != data.token or is_expired(token.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token.",
        )

    user.is_active = True
    db.delete(token)
    db.commit()

    return MessageResponse(message="User account activated successfully.")


@router.post(
    "/resend-activation/",
    response_model=MessageResponse,
    summary="Resend the activation token",
    description=(
        "Generates a new activation token (valid for another 24 hours) and "
        "sends it to the email. The response is always the same, so it does "
        "not reveal whether the email is registered."
    ),
)
def resend_activation(
    data: ResendActivationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is not None and not user.is_active:
        if user.activation_token is not None:
            db.delete(user.activation_token)
            db.flush()

        new_token = build_activation_token(user.id)
        db.add(new_token)
        db.commit()

        background_tasks.add_task(send_activation_email, email, new_token.token)

    return MessageResponse(
        message="If your account exists and is not activated, "
        "a new activation token has been sent."
    )
