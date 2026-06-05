import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base, get_db
import app.models

DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_sqlite_fk_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(
    engine,
    autocommit=False,
    autoflush=False
)

@pytest.fixture
def db():
    db = SessionLocal()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db: Session):
    fastapi_app.dependency_overrides[get_db] = lambda: db
    client = TestClient(fastapi_app)

    try:
        yield client
    finally:
        fastapi_app.dependency_overrides.clear()