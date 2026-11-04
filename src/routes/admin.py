from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import require_groups
from src.models import User, UserGroup, UserGroupEnum
from src.schemas.accounts import ChangeGroupRequest, UserAdminResponse

from src.schemas.cart import CartResponse
from src.services.cart import get_cart_view

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_groups(UserGroupEnum.ADMIN))],
)


def _to_response(user: User) -> UserAdminResponse:
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        group=user.group.name,
    )


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return user


@router.patch(
    "/users/{user_id}/group/",
    response_model=UserAdminResponse,
    summary="Change the group of a user",
    description="Moves the user to the USER, MODERATOR or ADMIN group. Admin only.",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Only admins can do this"},
        404: {"description": "User not found"},
    },
)
def change_user_group(
    user_id: int, data: ChangeGroupRequest, db: Session = Depends(get_db)
):
    user = _get_user_or_404(db, user_id)

    group = db.scalar(select(UserGroup).where(UserGroup.name == data.group))
    if group is None:
        group = UserGroup(name=data.group)
        db.add(group)
        db.flush()

    user.group_id = group.id
    db.commit()
    db.refresh(user)

    return _to_response(user)


@router.post(
    "/users/{user_id}/activate/",
    response_model=UserAdminResponse,
    summary="Activate a user account manually",
    description=(
        "Activates the account without an activation token and deletes the "
        "pending token, if any. Admin only."
    ),
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Only admins can do this"},
        404: {"description": "User not found"},
    },
)
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)

    user.is_active = True
    if user.activation_token is not None:
        db.delete(user.activation_token)
    db.commit()
    db.refresh(user)

    return _to_response(user)


@router.get(
    "/users/{user_id}/cart/",
    response_model=CartResponse,
    summary="View the cart of a user",
    description="Returns the cart of any user for analysis or troubleshooting. Admin only.",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Only admins can do this"},
        404: {"description": "User not found"},
    },
)
def view_user_cart(user_id: int, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    return get_cart_view(db, user.id)
