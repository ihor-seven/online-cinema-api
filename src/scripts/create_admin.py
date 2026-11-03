import sys

from sqlalchemy import select

from src.database import SessionLocal
from src.models import User, UserGroup, UserGroupEnum
from src.security import hash_password, validate_password_strength


def create_admin(email: str, password: str) -> None:
    validate_password_strength(password)

    db = SessionLocal()
    try:
        for name in UserGroupEnum:
            if db.scalar(select(UserGroup).where(UserGroup.name == name)) is None:
                db.add(UserGroup(name=name))
        db.flush()

        admin_group = db.scalar(
            select(UserGroup).where(UserGroup.name == UserGroupEnum.ADMIN)
        )
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            user = User(
                email=email.lower(),
                hashed_password=hash_password(password),
                is_active=True,
                group_id=admin_group.id,
            )
            db.add(user)
        else:
            user.group_id = admin_group.id
            user.is_active = True

        db.commit()
        print(f"Admin {email} is ready.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m src.scripts.create_admin <email> <password>")
        sys.exit(1)
    create_admin(sys.argv[1], sys.argv[2])