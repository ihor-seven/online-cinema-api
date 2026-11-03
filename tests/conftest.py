import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import app

from sqlalchemy import select

from src.models import UserGroup, UserGroupEnum, User
from src.security import create_access_token, hash_password

from decimal import Decimal
from src.models import Certification, Movie


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "src.routes.accounts.send_activation_email",
        lambda email, token: sent.append((email, token)),
    )
    return sent


@pytest.fixture(autouse=True)
def sent_reset_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "src.routes.passwords.send_password_reset_email",
        lambda email, token: sent.append((email, token)),
    )
    return sent


@pytest.fixture
def create_user(db_session):
    def _create(
        email="user@example.com",
        password="Test1234!",
        group=UserGroupEnum.USER,
        is_active=True,
    ):
        group_obj = db_session.scalar(select(UserGroup).where(UserGroup.name == group))
        if group_obj is None:
            group_obj = UserGroup(name=group)
            db_session.add(group_obj)
            db_session.flush()
        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_active=is_active,
            group_id=group_obj.id,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _create


@pytest.fixture
def auth_headers():
    def _headers(user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers

@pytest.fixture
def create_movie(db_session):
    def _create(name="Inception", year=2010, time=148, imdb=8.8, votes=1000, price="9.99"):
        certification = db_session.scalar(
            select(Certification).where(Certification.name == "PG-13")
        )
        if certification is None:
            certification = Certification(name="PG-13")
            db_session.add(certification)
            db_session.flush()

        movie = Movie(
            name=name,
            year=year,
            time=time,
            imdb=imdb,
            votes=votes,
            description=f"Description of {name}",
            price=Decimal(price),
            certification_id=certification.id,
        )
        db_session.add(movie)
        db_session.commit()
        return movie

    return _create
