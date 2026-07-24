from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas.search import SearchResponse
from backend.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/", response_model=SearchResponse)
def search(q: str = Query(""), db: Session = Depends(get_db)):
    results = SearchService.search(db, q)
    return {"query": q, "results": results}
