from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.nicknames.errors import NicknameError
from app.api.v1.nicknames.schemas import (
    NicknameAvailabilityResponse,
    NicknameRecommendationResponse,
    NicknameSelectionRequest,
    NicknameSelectionResponse,
)
from app.api.v1.nicknames.service import NicknameService
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/nicknames", tags=["닉네임"])


def _nickname_error_response(error: NicknameError) -> JSONResponse:
    status_code = status.HTTP_409_CONFLICT if error.code == "NICKNAME_ALREADY_EXISTS" else status.HTTP_400_BAD_REQUEST
    return JSONResponse(
        status_code=status_code,
        content={"available": False, "code": error.code, "message": error.message},
    )


@router.get("/recommendation", response_model=NicknameRecommendationResponse)
def recommend_nickname(db: Session = Depends(get_db)):
    try:
        return NicknameRecommendationResponse(nickname=NicknameService(db).recommend())
    except NicknameError as error:
        return _nickname_error_response(error)


@router.get("/availability", response_model=NicknameAvailabilityResponse)
def check_nickname_availability(
    nickname: str = Query(default=""),
    db: Session = Depends(get_db),
):
    try:
        return NicknameAvailabilityResponse(**NicknameService(db).check_availability(nickname))
    except NicknameError as error:
        return _nickname_error_response(error)


@router.post("/selection", response_model=NicknameSelectionResponse)
def select_nickname(
    payload: NicknameSelectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        updated = NicknameService(db).select(user, payload.nickname)
        return NicknameSelectionResponse(id=updated.id, nickname=updated.nickname)
    except NicknameError as error:
        return _nickname_error_response(error)
