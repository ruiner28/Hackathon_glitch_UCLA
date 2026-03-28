from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/version")
async def version():
    return {"version": "0.1.0", "name": "VisualCS"}
