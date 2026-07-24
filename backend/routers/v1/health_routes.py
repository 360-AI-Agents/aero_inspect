from fastapi import APIRouter
from backend.config import settings

router = APIRouter(tags=["Health"])


@router.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running"
    }


@router.get("/health")
def health_check():
    return {"status": "ok"}