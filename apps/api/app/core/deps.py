from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.user import User
from app.services.auth.session import get_user_from_session_cookie


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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid session cookie (use on protected API routes)."""
    user = await get_user_from_session_cookie(request, db)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
