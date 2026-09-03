from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.local import schema, service
from app.core.db import get_db

router = APIRouter(prefix="/api/v1/local", tags=["갖가지"])


@router.get("/danger-signals", response_model=schema.DangerSignalListResponse)
def list_danger_signals(
    sigungu: str | None = None,
    q: str | None = None,
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return service.list_danger_signals(db, sigungu=sigungu, q=q, limit=limit)


@router.get("/recommend-place", response_model=schema.PlaceRecommendationResponse)
def recommend_place(query: str = Query(..., min_length=1, max_length=100)):
    return service.recommend_place(query)
