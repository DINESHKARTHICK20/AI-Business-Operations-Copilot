import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import Base, DATABASE_URL, IS_POSTGRES
import backend.models  # Ensure all models are registered

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Returns database URL from environment or alembic config."""
    db_url = (os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL") or "").strip()
    if db_url:
        if db_url.startswith("mysql://"):
            db_url = "mysql+pymysql://" + db_url[len("mysql://"):]
        elif db_url.startswith("postgres://"):
            db_url = "postgresql+psycopg://" + db_url[len("postgres://"):]
        elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
            db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]
        return db_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
