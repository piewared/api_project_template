"""Database engine and session factory used across the application."""

from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger
from sqlalchemy import text
from sqlmodel import Session, create_engine

from src.app.runtime.context import get_config


class DbSessionService:
    def __init__(self):
        main_config = get_config()
        db_config = main_config.database

        # Production-optimized engine configuration
        engine_kwargs = {
            # Connection pool settings
            "pool_size": db_config.pool_size,
            "max_overflow": db_config.max_overflow,
            "pool_timeout": db_config.pool_timeout,
            "pool_recycle": db_config.pool_recycle,
            # Performance optimizations
            "pool_pre_ping": True,  # Validate connections before use
            "pool_reset_on_return": "commit",  # Auto-commit on connection return
            # Logging - disable echo in production for performance
            "echo": main_config.app.environment != "production",
            "echo_pool": main_config.app.environment == "development",
            # Connection behavior
            "connect_args": self._get_connect_args(main_config),
        }

        # Additional async pool settings for PostgreSQL
        if "postgresql" in db_config.url:
            engine_kwargs.update(
                {
                    # Async-specific optimizations
                    "poolclass": None,  # Use default async pool
                }
            )

        self._engine = create_engine(main_config.database.connection_string, **engine_kwargs)

        # Log configuration for monitoring
        if main_config.app.environment == "production":
            logger.info(
                "Database engine initialized",
                extra={
                    "pool_size": db_config.pool_size,
                    "max_overflow": db_config.max_overflow,
                    "pool_timeout": db_config.pool_timeout,
                    "pool_recycle": db_config.pool_recycle,
                },
            )

    def _get_connect_args(self, config) -> dict:
        """Get database-specific connection arguments for optimization."""
        connect_args = {}

        if "postgresql" in config.database.url:
            # PostgreSQL-specific optimizations
            connect_args.update(
                {
                    # Connection-level optimizations
                    "server_settings": {
                        # Reduce memory usage for small queries
                        "jit": "off",
                        # Optimize for application workloads
                        "application_name": f"{config.app.environment}_api",
                    },
                    # Statement timeout for long-running queries (30 seconds)
                    "command_timeout": 30,
                }
            )

            # Production-specific PostgreSQL settings
            if config.app.environment == "production":
                connect_args["server_settings"].update(
                    {
                        # Production query optimization
                        "random_page_cost": "1.1",  # SSD optimization
                        "effective_cache_size": "1GB",  # Adjust based on available RAM
                    }
                )

        elif "sqlite" in config.database.url:
            # SQLite-specific optimizations
            connect_args.update(
                {
                    "check_same_thread": False,  # Required for async
                    "timeout": 20,  # Lock timeout
                }
            )

            if config.app.environment == "production":
                logger.warning(
                    "SQLite is not recommended for production use. "
                    "Consider PostgreSQL for better performance and reliability."
                )

        return connect_args

    def get_session(self) -> Session:
        """Return a new SQLModel session bound to the shared engine."""
        return Session(
            self._engine,
            expire_on_commit=False,  # Prevent lazy loading issues
            autoflush=True,  # Auto-flush before queries
            autocommit=False,  # Explicit transaction control
        )

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Context manager style helper for repositories and tests."""
        db = self.get_session()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            # Log database errors for monitoring
            logger.error(
                "Database transaction failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            raise
        finally:
            db.close()

    def health_check(self) -> bool:
        """Perform a health check on the database connection."""
        try:
            with self._engine.connect() as connection:
                # Simple query to test connectivity
                connection.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(
                "Database health check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return False

    def get_pool_status(self) -> dict:
        """Get current connection pool status for monitoring."""
        pool = self._engine.pool
        return {
            "size": getattr(pool, "size", lambda: 0)(),
            "checked_in": getattr(pool, "checkedin", lambda: 0)(),
            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
            "overflow": getattr(pool, "overflow", lambda: 0)(),
            "invalid": getattr(pool, "invalid", lambda: 0)(),
        }
