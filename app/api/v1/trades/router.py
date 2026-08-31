from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.trades import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/trades", tags=["중고거래"])


@router.post("/products", response_model=schema.ProductCreated, status_code=status.HTTP_201_CREATED)
def create_product(
    body: schema.ProductCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = service.create_product(db, user, body)
    return schema.ProductCreated(id=product.id)


@router.get("/products", response_model=schema.ProductListResponse)
def list_products(
    region_id: int | None = None,
    category: str | None = None,
    trade_status: schema.TradeStatus | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
):
    return service.list_products(db, region_id, category, trade_status, q, page, size)


@router.get("/products/{product_id}", response_model=schema.ProductDetailResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return service.get_product_detail(db, product_id)


@router.patch("/products/{product_id}/status", response_model=schema.ProductDetailResponse)
def update_product_status(
    product_id: int,
    body: schema.ProductStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.update_product_status(db, user, product_id, body.trade_status)
    return service.get_product_detail(db, product_id)


@router.patch("/products/{product_id}", response_model=schema.ProductDetailResponse)
def update_product(
    product_id: int,
    body: schema.ProductUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.update_product(db, user, product_id, body)
    return service.get_product_detail(db, product_id)
