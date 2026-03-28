from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from app.db.session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_app_settings() -> Settings:
    return get_settings()
