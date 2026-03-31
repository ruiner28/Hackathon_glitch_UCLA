import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import APPS_API_ROOT, REPO_ROOT, get_settings

logger = logging.getLogger(__name__)


def _log_env_hints_for_gemini() -> None:
    """Help debug 'invalid API key' when .env was updated but another source wins."""
    root_env = REPO_ROOT / ".env"
    api_env = APPS_API_ROOT / ".env"
    if root_env.is_file() and api_env.is_file():
        logger.info(
            "Both %s and %s exist; for duplicate keys the later file (apps/api/.env) wins.",
            root_env,
            api_env,
        )
    if os.environ.get("GEMINI_API_KEY"):
        logger.warning(
            "GEMINI_API_KEY is set in the shell environment; it overrides .env files. "
            "If you edited .env but nothing changes, run: unset GEMINI_API_KEY && pnpm dev:api"
        )
    s = get_settings()
    k = (s.GEMINI_API_KEY or "").strip()
    if s.LLM_PROVIDER == "google" and k:
        logger.info(
            "LLM_PROVIDER=google: GEMINI_API_KEY length=%s (AI Studio keys usually start with 'AIza').",
            len(k),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db

    _log_env_hints_for_gemini()
    await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="VisualCS API",
        description="Backend API for VisualCS — AI-powered CS video lesson generator",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Browsers treat localhost vs 127.0.0.1 as different Origins; allow both for local dev.
    frontend = (settings.FRONTEND_URL or "").rstrip("/")
    cors_origins = list(
        dict.fromkeys(
            [
                frontend,
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        )
    )
    cors_origins = [o for o in cors_origins if o]

    cors_kwargs: dict = {
        "allow_origins": cors_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.APP_ENV == "development":
        # Any dev port (3000, 3001, …) for localhost / 127.0.0.1
        cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

    application.add_middleware(CORSMiddleware, **cors_kwargs)

    @application.exception_handler(ResponseValidationError)
    async def response_validation_handler(
        request: Request, exc: ResponseValidationError
    ) -> JSONResponse:
        logger.exception(
            "Response validation failed on %s %s", request.method, request.url.path
        )
        payload: dict = {
            "detail": str(exc),
            "type": "ResponseValidationError",
        }
        if settings.APP_ENV == "development":
            payload["traceback"] = traceback.format_exc()
        return JSONResponse(status_code=500, content=payload)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        payload: dict = {
            "detail": str(exc),
            "type": type(exc).__name__,
        }
        if settings.APP_ENV == "development":
            payload["traceback"] = traceback.format_exc()
        return JSONResponse(status_code=500, content=payload)

    application.include_router(api_router)

    return application


app = create_app()
