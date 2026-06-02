import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models

DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
