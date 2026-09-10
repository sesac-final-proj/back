from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.chats.schema import MessageResponse
from app.api.v1.wallet import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/wallet", tags=["당근페이"])


@router.get("/me", response_model=schema.WalletBalanceResponse)
def get_my_balance(user: User = Depends(get_current_user)):
    return service.get_balance(user)


@router.post(
    "/{chat_room_id}/payments",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_payment(
    chat_room_id: int,
    body: schema.PaymentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.send_payment(db, user, chat_room_id, body)


@router.post("/charge", response_model=schema.WalletBalanceResponse)
def charge_wallet(
    body: schema.ChargeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.charge_wallet(db, user, body.amount)


@router.post("/pay", response_model=schema.WalletBalanceResponse)
def pay_by_qr(
    body: schema.QrPayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.pay_by_qr(db, user, body)


# QR 발급용 — 어드민이 가맹점 이름을 등록하고 받은 id로
# "<프론트도메인>/carrot?pay=<id>" URL을 만들어 QR로 인쇄한다.
@router.post("/stores", response_model=schema.StoreResponse, dependencies=[Depends(require_admin)])
def create_store(body: schema.StoreCreateRequest, db: Session = Depends(get_db)):
    return service.create_store(db, body)


# 손님 앱이 QR(또는 그 URL)을 스캔한 뒤 결제 화면에 표시할 가맹점 이름을 조회.
@router.get("/stores/{store_id}", response_model=schema.StoreResponse)
def get_store(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_store(db, store_id)


@router.get("/transactions/{transaction_id}", response_model=schema.PaymentDetailResponse)
def get_payment_detail(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_payment_detail(db, user, transaction_id)
