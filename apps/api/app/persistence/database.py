from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

SCHEMA_REVISION = "seva_0006"


def database(url: str):
    """Explicit injection only. Never load the prototype's .env or create tables."""
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL with psycopg is required")
    if (
        parsed.host not in {"localhost", "127.0.0.1", "::1"}
        and parsed.query.get("sslmode") != "verify-full"
    ):
        raise ValueError("Nonlocal PostgreSQL requires sslmode=verify-full")
    engine = create_engine(
        parsed,
        pool_size=5,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c timezone=UTC -c lock_timeout=5000 -c statement_timeout=15000",
        },
    )
    return engine, sessionmaker(engine, expire_on_commit=False)
