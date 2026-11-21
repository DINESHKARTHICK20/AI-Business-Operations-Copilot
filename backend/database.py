"""
Database Engine & Connection Pool Adapter
AI Business Operations Copilot - Production Architecture

Supports both PostgreSQL (via psycopg 3 and SQLAlchemy QueuePool) and SQLite fallback for local development.
"""

import os
import re
import logging
from pathlib import Path
from typing import Generator, Dict, Any, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool, NullPool

logger = logging.getLogger("bizops.database")

# Environment configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Normalize postgres:// to postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

IS_POSTGRES = DATABASE_URL.startswith("postgresql")

if IS_POSTGRES:
    # Production / Staging PostgreSQL Engine with Enterprise Connection Pooling
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,       # Health-checks connections before checkout
        pool_recycle=1800,        # Recycles idle connections every 30 minutes
        pool_timeout=30,          # 30 second checkout timeout
        echo=False
    )
    logger.info("Configured PostgreSQL database engine with QueuePool.")
else:
    # Development / Fallback SQLite Engine
    SQLITE_PATH = Path(os.environ.get("DB_PATH", "backend/ai_bizops.db")).resolve()
    engine = create_engine(
        f"sqlite:///{SQLITE_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Enforce SQLite foreign keys on every connection
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA busy_timeout = 30000;")
        cursor.close()

    logger.info("Configured SQLite database engine (fallback mode).")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_safe_db_info(url_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns sanitized database connection information without exposing passwords or secrets.
    """
    target_url = url_override or DATABASE_URL
    if not target_url:
        return {
            "engine": "SQLite",
            "dialect": "sqlite",
            "host": "localhost",
            "database": str(Path(os.environ.get("DB_PATH", "backend/ai_bizops.db")).name),
            "is_postgres": False,
            "ssl_enabled": False,
        }

    try:
        parsed = urlparse(target_url)
        # Mask password
        netloc = parsed.netloc
        if "@" in netloc:
            user_part, host_part = netloc.split("@", 1)
            username = user_part.split(":", 1)[0]
            masked_netloc = f"{username}:***@{host_part}"
        else:
            masked_netloc = netloc

        return {
            "engine": "PostgreSQL" if "postgresql" in parsed.scheme else parsed.scheme,
            "dialect": parsed.scheme,
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/"),
            "is_postgres": "postgresql" in parsed.scheme,
            "ssl_enabled": "sslmode" in parsed.query,
            "masked_target": f"{parsed.scheme}://{masked_netloc}{parsed.path}"
        }
    except Exception as e:
        return {
            "engine": "Unknown",
            "error": str(e),
            "is_postgres": False
        }


def test_database_connection(url_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Tests live database reachability and executes a test query.
    Returns safe status dictionary with zero credential leakage.
    """
    test_url = url_override or DATABASE_URL
    safe_info = get_safe_db_info(test_url)

    if not test_url:
        # Test SQLite connection
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT 1;")).scalar()
                fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
                return {
                    "status": "connected",
                    "safe_info": safe_info,
                    "test_scalar": res,
                    "foreign_keys_active": fk == 1,
                    "error": None
                }
        except Exception as e:
            return {
                "status": "failed",
                "safe_info": safe_info,
                "test_scalar": None,
                "foreign_keys_active": False,
                "error": str(e)
            }

    # Test PostgreSQL connection with isolated engine
    test_eng = None
    try:
        test_eng = create_engine(
            test_url,
            poolclass=NullPool,
            connect_args={"connect_timeout": 5}
        )
        with test_eng.connect() as conn:
            val = conn.execute(text("SELECT 1;")).scalar()
            ver = conn.execute(text("SELECT version();")).scalar()
            return {
                "status": "connected",
                "safe_info": safe_info,
                "test_scalar": val,
                "server_version": str(ver).split(" ")[0] if ver else "PostgreSQL",
                "error": None
            }
    except Exception as exc:
        err_msg = str(exc)
        # Strip any accidental passwords from exception message
        sanitized_err = re.sub(r':[^:@]+@', ':***@', err_msg)
        return {
            "status": "failed",
            "safe_info": safe_info,
            "test_scalar": None,
            "server_version": None,
            "error": sanitized_err
        }
    finally:
        if test_eng:
            try:
                test_eng.dispose()
            except Exception:
                pass
