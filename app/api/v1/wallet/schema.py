from datetime import datetime

from pydantic import BaseModel, Field


class WalletBalanceResponse(BaseModel):
    balance: int


class PaymentCreateRequest(BaseModel):
    amount: int = Field(gt=0)


class ChargeCreateRequest(BaseModel):
    amount: int = Field(gt=0)


class QrPayRequest(BaseModel):
    merchant_name: str
    amount: int = Field(gt=0)


class PaymentDetailResponse(BaseModel):
    """상세내역 화면(9-2. 거래한 사람/일시/충전금액/거래후잔액)용.

    "충전계좌"는 실제 계좌 연동이 없는 mock이라 프론트에서 정적 텍스트로
    보여주면 되고, 여기선 실제로 존재하는 값만 내려준다.
    """

    id: int
    chat_room_id: int
    product_id: int | None
    product_title: str | None
    product_thumbnail_url: str | None
    counterpart_nickname: str | None
    # 이 응답을 보는 사람이 보낸 사람인지(True) 받은 사람인지(False) — 문구 분기용
    # ("송금했어요" vs "받았어요").
    is_sender: bool
    amount: int
    balance_after: int
    created_at: datetime
