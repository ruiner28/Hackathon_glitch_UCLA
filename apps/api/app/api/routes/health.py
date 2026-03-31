from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import APPS_API_ROOT, REPO_ROOT, get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/version")
async def version():
    return {"version": "0.1.0", "name": "VisualCS"}


@router.get("/health/gemini-env")
async def gemini_env_diagnostics():
    """Dev-only: confirm which .env paths exist and whether a key is loaded (never exposes full key)."""
    s = get_settings()
    if s.APP_ENV != "development":
        return JSONResponse(
            status_code=404,
            content={"detail": "Not available outside development"},
        )
    key = (s.GEMINI_API_KEY or "").strip()
    root_env = REPO_ROOT / ".env"
    api_env = APPS_API_ROOT / ".env"
    return {
        "repo_root": str(REPO_ROOT),
        "env_files": {
            str(root_env): root_env.is_file(),
            str(api_env): api_env.is_file(),
        },
        "llm_provider": s.LLM_PROVIDER,
        "gemini_model": s.GEMINI_MODEL,
        "gemini_api_key_loaded": bool(key),
        "gemini_api_key_length": len(key),
        "gemini_api_key_prefix": f"{key[:4]}…" if len(key) >= 4 else None,
        "looks_like_ai_studio_key": key.startswith("AIza") if key else False,
        "hint": (
            "If length is 0, fix .env path or variable name. If length > 0 but Google returns API_KEY_INVALID, "
            "the key is rejected on Google's side: (1) Google Cloud Console → APIs & Services → Credentials → "
            "your key → API restrictions: for testing use 'Don't restrict key', or allow 'Generative Language API'. "
            "(2) Enable the Generative Language API for the project. "
            f"(3) Test with curl using model {s.GEMINI_MODEL!r} and your key as the query parameter."
        ),
    }
