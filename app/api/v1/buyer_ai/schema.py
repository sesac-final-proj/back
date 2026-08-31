from typing import Literal

from pydantic import BaseModel

from app.api.v1.trades.schema import PriceRangeResponse


class PriceEvaluationRequest(BaseModel):
    product_title: str
    category: str
    listed_price: int
    region: str


class PriceEvaluationResponse(BaseModel):
    verdict: Literal["적정", "고가", "저가", "평가불가"]
    price_range: PriceRangeResponse
    diff_percent: float | None


class QuestionSuggestionRequest(BaseModel):
    product_description: str


class QuestionSuggestionResponse(BaseModel):
    questions: list[str]
