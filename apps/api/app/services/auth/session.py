"""Resolve signed-in user from opaque session cookie (server-side session row)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import AuthSession, User


async def get_user_from_session_cookie(
    request: Request,
    db: AsyncSession,
) -> User | None:
    settings = get_settings()
    sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not sid:
        return None

    result = await db.execute(
        select(AuthSession, User)
        .join(User, AuthSession.user_id == User.id)
        .where(AuthSession.id == sid)
    )
    row = result.first()
    if not row:
        return None

    auth_row, user = row
    now = datetime.now(timezone.utc)
    if auth_row.revoked_at is not None:
        return None
    if auth_row.expires_at <= now:
        return None
    return user
