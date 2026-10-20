
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from src.core.config_core import get_settings
from src.db.session_db import Base
from src.models.user_models import User  # noqa: F401

# Alembic configuration
config = context.config

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("%", "%%"),
)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy models metadata
target_metadata = Base.metadata

# Keep AP-Auth migration tracking separate from AP-Core.
AUTH_VERSION_TABLE = "auth_alembic_version"

# AP-Auth currently owns only the users table.
# This prevents Alembic from treating AP-Core tables as removed.
AUTH_TABLES = {"users"}


def include_name(name, type_, parent_names):
    """Include only tables owned by AP-Auth during autogeneration."""
    if type_ == "table":
        return name in AUTH_TABLES
    return True


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=AUTH_VERSION_TABLE,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=AUTH_VERSION_TABLE,
            include_name=include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
