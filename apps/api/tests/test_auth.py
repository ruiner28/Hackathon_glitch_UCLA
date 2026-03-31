"""Contract tests: auth endpoints (session cookie, OAuth redirect, logout)."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_me_unauthorized():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_session_ok():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_google_login_redirect_when_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:3000/api/auth/callback/google",
    )

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/auth/google", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get("location") or ""
    assert "accounts.google.com" in loc
    assert "test-client-id" in loc


def _clear_google_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force OAuth unset: override .env and all config aliases with empty strings."""
    for key in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
        "AUTH_GOOGLE_SECRET",
        "GOOGLE_CLIENT_SECRET",
    ):
        monkeypatch.setenv(key, "")


@pytest.mark.asyncio
async def test_google_login_503_when_not_configured(monkeypatch):
    _clear_google_oauth_env(monkeypatch)

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/auth/google", follow_redirects=False)
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_callback_rejects_invalid_state(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:3000/api/auth/callback/google",
    )

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(
            "/api/auth/callback/google",
            params={"code": "fake", "state": "not-matching-cookie"},
            follow_redirects=False,
        )
    assert r.status_code == 400
