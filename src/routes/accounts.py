import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.schemas.accounts import UserRegisterRequest, UserRegisterResponse
from src.security import hash_password

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])

ACTIVATION_TOKEN_TTL_HOURS = 24


@router.post(
    "/register/",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new inactive account in the USER group and generates "
        "an activation token valid for 24 hours. "
        "The password must contain at least 8 characters, an uppercase "
        "letter, a lowercase letter, a digit and a special character."
    ),
    responses={
        409: {"description": "A user with this email already exists"},
        422: {"description": "Invalid email or weak password"},
    },
)
def register_user(data: UserRegisterRequest, db: Session = Depends(get_db)):
    email = data.email.lower()

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
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

    activation_token = ActivationToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=ACTIVATION_TOKEN_TTL_HOURS),
    )
    db.add(activation_token)
    db.commit()
    db.refresh(user)

    return user