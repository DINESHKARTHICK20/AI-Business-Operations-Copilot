"""
Database Engine & Connection Pool Adapter
AI Business Operations Copilot - Production & Staging Architecture

Supports MySQL (via PyMySQL and SQLAlchemy QueuePool), PostgreSQL, and SQLite fallback for local development.
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

# Environment configuration - Check DATABASE_URL or MYSQL_URL
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("MYSQL_URL")
    or os.environ.get("MYSQL_DATABASE_URL")
    or ""
).strip()

# Normalize connection string
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = "mysql+pymysql://" + DATABASE_URL[len("mysql://"):]
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

IS_MYSQL = DATABASE_URL.startswith("mysql")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

if IS_MYSQL:
    # Production / Staging MySQL Engine with Enterprise Connection Pooling (InnoDB, utf8mb4)
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,       # Health-checks connections before checkout
        pool_recycle=1800,        # Recycles idle connections every 30 minutes (prevents MySQL 8h timeout)
        pool_timeout=30,          # 30 second checkout timeout
        connect_args={"charset": "utf8mb4"},
        echo=False
    )
    logger.info("Configured MySQL database engine with QueuePool (InnoDB, utf8mb4).")

elif IS_POSTGRES:
    # Production / Staging PostgreSQL Engine with Enterprise Connection Pooling
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=30,
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
            "is_mysql": False,
            "is_postgres": False,
            "ssl_enabled": False,
        }

    try:
        parsed = urlparse(target_url)
        netloc = parsed.netloc
        if "@" in netloc:
            user_part, host_part = netloc.split("@", 1)
            username = user_part.split(":", 1)[0]
            masked_netloc = f"{username}:***@{host_part}"
        else:
            masked_netloc = netloc

        dialect = parsed.scheme.split("+")[0]
        engine_name = "MySQL" if "mysql" in parsed.scheme else ("PostgreSQL" if "postgres" in parsed.scheme else dialect)
        default_port = 3306 if "mysql" in parsed.scheme else 5432

        return {
            "engine": engine_name,
            "dialect": parsed.scheme,
            "host": parsed.hostname or "localhost",
            "port": parsed.port or default_port,
            "database": parsed.path.lstrip("/"),
            "is_mysql": "mysql" in parsed.scheme,
            "is_postgres": "postgres" in parsed.scheme,
            "ssl_enabled": "ssl" in parsed.query or "sslmode" in parsed.query,
            "masked_target": f"{parsed.scheme}://{masked_netloc}{parsed.path}"
        }
    except Exception as e:
        return {
            "engine": "Unknown",
            "error": str(e),
            "is_mysql": False,
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
                    "server_version": "SQLite 3.x",
                    "error": None
                }
        except Exception as e:
            return {
                "status": "failed",
                "safe_info": safe_info,
                "test_scalar": None,
                "foreign_keys_active": False,
                "server_version": None,
                "error": str(e)
            }

    # Test MySQL / PostgreSQL connection with isolated engine
    test_eng = None
    try:
        connect_args = {}
        if "mysql" in test_url:
            connect_args = {"charset": "utf8mb4", "connect_timeout": 5}
        else:
            connect_args = {"connect_timeout": 5}

        test_eng = create_engine(
            test_url,
            poolclass=NullPool,
            connect_args=connect_args
        )
        with test_eng.connect() as conn:
            val = conn.execute(text("SELECT 1;")).scalar()
            ver = conn.execute(text("SELECT VERSION();")).scalar()
            return {
                "status": "connected",
                "safe_info": safe_info,
                "test_scalar": val,
                "server_version": str(ver) if ver else "MySQL",
                "error": None
            }
    except Exception as exc:
        err_msg = str(exc)
        # Strip passwords from exception message
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
