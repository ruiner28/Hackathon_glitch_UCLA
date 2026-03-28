from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.core.config import get_settings
        settings = get_settings()

        kwargs: dict = {"echo": False}
        if not settings.DATABASE_URL.startswith("sqlite"):
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 10

        _engine = create_async_engine(settings.DATABASE_URL, **kwargs)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory for direct use with context managers."""
    return _get_session_factory()


async def get_session() -> AsyncSession:
    """Create and return a new async session."""
    factory = _get_session_factory()
    return factory()


async def init_db() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
