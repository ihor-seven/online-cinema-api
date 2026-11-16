from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.database import get_db
from src.models import User
from src.security import verify_password

REALM = "Online Cinema API docs"
basic_auth = HTTPBasic(realm=REALM)


def get_docs_user(
    credentials: HTTPBasicCredentials = Depends(basic_auth),
    db: Session = Depends(get_db),
) -> User:
    """Allow access to the docs only to active users (email + password)."""
    user = db.scalar(select(User).where(User.email == credentials.username.lower()))

    if (
        user is None
        or not user.is_active
        or not verify_password(credentials.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": f'Basic realm="{REALM}"'},
        )
    return user


router = APIRouter(include_in_schema=False, dependencies=[Depends(get_docs_user)])


@router.get("/docs")
def swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=f"{settings.app_name} - Swagger UI"
    )


@router.get("/redoc")
def redoc() -> HTMLResponse:
    return get_redoc_html(
        openapi_url="/openapi.json", title=f"{settings.app_name} - ReDoc"
    )


@router.get("/openapi.json")
def openapi_schema(request: Request) -> dict[str, Any]:
    return request.app.openapi()
