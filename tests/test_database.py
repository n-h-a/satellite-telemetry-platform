from app.database import _normalize_database_url


def test_normalize_database_url_rewrites_bare_postgresql_scheme():
    assert _normalize_database_url("postgresql://user:pass@host:5432/db") == \
        "postgresql+psycopg://user:pass@host:5432/db"


def test_normalize_database_url_rewrites_legacy_postgres_scheme():
    assert _normalize_database_url("postgres://user:pass@host:5432/db") == \
        "postgresql+psycopg://user:pass@host:5432/db"


def test_normalize_database_url_leaves_psycopg_scheme_unchanged():
    url = "postgresql+psycopg://user:pass@host:5432/db"
    assert _normalize_database_url(url) == url


def test_normalize_database_url_leaves_other_schemes_unchanged():
    url = "sqlite:///:memory:"
    assert _normalize_database_url(url) == url
