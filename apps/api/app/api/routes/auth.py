"""Google OAuth login, callback, session cookie, logout, and /me."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_db
from app.models.user import AuthSession, User
from app.services.auth.google_oauth import (
    exchange_authorization_code,
    verify_google_id_token_jwt,
)
from app.services.auth.session import get_user_from_session_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "openid email profile"


def _cookie_secure() -> bool:
    s = get_settings()
    return s.APP_ENV == "production" or s.FRONTEND_URL.strip().lower().startswith(
        "https://"
    )


def _safe_next_path(raw: str | None) -> str:
    """Prevent open redirects: only same-app relative paths."""
    if not raw:
        return "/"
    path = raw.strip()
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return path.split("?")[0].split("#")[0] or "/"


@router.get("/google")
async def google_login(
    next: str | None = None,
) -> RedirectResponse:
    """Start OAuth: set short-lived state (+ optional post-login path) cookies, redirect to Google."""
    settings = get_settings()
    if not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured (set GOOGLE_OAUTH_CLIENT_ID/SECRET).",
        )

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(url=url, status_code=302)
    secure = _cookie_secure()
    response.set_cookie(
        key=settings.OAUTH_STATE_COOKIE_NAME,
        value=state,
        max_age=settings.OAUTH_STATE_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    next_path = _safe_next_path(next)
    if next_path != "/":
        response.set_cookie(
            key=settings.OAUTH_NEXT_COOKIE_NAME,
            value=quote(next_path, safe="/"),
            max_age=settings.OAUTH_STATE_MAX_AGE_SEC,
            httponly=True,
            samesite="lax",
            secure=secure,
            path="/",
        )
    return response


@router.get("/callback/google")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """OAuth callback: verify state, exchange code, verify id_token, upsert user, set session cookie."""
    settings = get_settings()
    frontend = settings.FRONTEND_URL.rstrip("/")

    if error:
        logger.warning("Google OAuth error param: %s", error)
        return RedirectResponse(
            url=f"{frontend}/login?error={quote(error)}",
            status_code=302,
        )

    if not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing code or state")

    cookie_state = request.cookies.get(settings.OAUTH_STATE_COOKIE_NAME)
    if not cookie_state or cookie_state != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    if not (
        settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured.",
        )

    try:
        tokens = await exchange_authorization_code(
            code=code,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("Token exchange failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed: {exc.response.text[:200]}",
        ) from exc

    id_token_jwt = tokens.get("id_token")
    if not id_token_jwt or not isinstance(id_token_jwt, str):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No id_token in token response",
        )

    try:
        claims = verify_google_id_token_jwt(
            id_token_jwt=id_token_jwt,
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID token: {exc}",
        ) from exc

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing sub claim")

    email = claims.get("email")
    if not email or not isinstance(email, str):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing email")

    name = claims.get("name")
    picture = claims.get("picture")

    result = await db.execute(
        select(User).where(User.provider == "google", User.provider_sub == sub)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            name=name if isinstance(name, str) else None,
            provider="google",
            provider_sub=sub,
            picture_url=picture if isinstance(picture, str) else None,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = email
        if isinstance(name, str):
            user.name = name
        if isinstance(picture, str):
            user.picture_url = picture

    # New session id (opaque); store only server-side
    new_session_id = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.SESSION_MAX_AGE_SEC
    )
    db.add(
        AuthSession(
            id=new_session_id,
            user_id=user.id,
            expires_at=expires_at,
        )
    )

    await db.commit()

    next_path = "/"
    raw_next = request.cookies.get(settings.OAUTH_NEXT_COOKIE_NAME)
    if raw_next:
        next_path = _safe_next_path(unquote(raw_next))

    redirect = RedirectResponse(url=f"{frontend}{next_path}", status_code=302)
    secure = _cookie_secure()
    redirect.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=new_session_id,
        max_age=settings.SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    redirect.delete_cookie(settings.OAUTH_STATE_COOKIE_NAME, path="/")
    redirect.delete_cookie(settings.OAUTH_NEXT_COOKIE_NAME, path="/")
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Revoke server session and clear cookie."""
    settings = get_settings()
    sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if sid:
        result = await db.execute(select(AuthSession).where(AuthSession.id == sid))
        row = result.scalar_one_or_none()
        if row:
            row.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    resp = JSONResponse({"ok": True})
    resp.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return resp


@router.get("/me")
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current user if session cookie is valid."""
    user = await get_user_from_session_cookie(request, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture_url": user.picture_url,
        "provider": user.provider,
    }
