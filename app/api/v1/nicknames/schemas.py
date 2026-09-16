from pydantic import BaseModel


class NicknameRecommendationResponse(BaseModel):
    nickname: str


class NicknameAvailabilityResponse(BaseModel):
    available: bool
    code: str
    message: str


class NicknameSelectionRequest(BaseModel):
    nickname: str


class NicknameSelectionResponse(BaseModel):
    id: int
    nickname: str
