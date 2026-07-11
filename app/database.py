import os
import threading

import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

def _normalize_database_url(url: str) -> str:
    # Managed Postgres providers commonly hand back a bare postgresql:// URL
    # (which SQLAlchemy resolves to psycopg2 — not installed) or the legacy
    # postgres:// scheme (which SQLAlchemy 2.0 rejects outright). Select the
    # psycopg3 driver explicitly in both cases.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL: str = os.getenv("DATABASE_URL")  # type: ignore[assignment]
REDIS_URL: str = os.getenv("REDIS_URL")         # type: ignore[assignment]

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

DATABASE_URL = _normalize_database_url(DATABASE_URL)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    engine,
    autocommit=False,
    autoflush=False
)

_redis_client = None
_redis_lock = threading.Lock()

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_redis():
    yield _get_redis_client()

def reset_redis_client():
    global _redis_client
    with _redis_lock:
        try:
            if _redis_client is not None:
                _redis_client.close()
        finally:
            _redis_client = None

def _get_redis_client():
    global _redis_client
    client = _redis_client
    if client is None:
        with _redis_lock:
            client = _redis_client
            if client is None:
                if not REDIS_URL:
                    raise RuntimeError("REDIS_URL environment variable is not set")
                # Short socket timeouts: a hung Redis must not stall request
                # threads, since every caller falls back to the database.
                client = redis.Redis.from_url(
                    REDIS_URL,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
                _redis_client = client
    return client
