"""Google OAuth2 code exchange and ID token verification."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def exchange_authorization_code(
    *,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens (access_token, id_token, …)."""
    async with httpx.AsyncClient() as client:
        res = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
    if res.status_code != 200:
        logger.warning("Google token exchange failed: %s %s", res.status_code, res.text[:500])
        res.raise_for_status()
    return res.json()


def verify_google_id_token_jwt(*, id_token_jwt: str, client_id: str) -> dict[str, Any]:
    """
    Verify ID token signature, issuer, audience (client_id), and expiry.
    Raises ValueError if invalid.
    """
    request = google_auth_requests.Request()
    info = google_id_token.verify_oauth2_token(id_token_jwt, request, client_id)
    iss = info.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        raise ValueError(f"Invalid token issuer: {iss!r}")
    if info.get("aud") != client_id:
        raise ValueError("Invalid token audience")
    return info
