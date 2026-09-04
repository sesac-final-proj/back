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


@router.get("/products/favorites", response_model=schema.ProductFavoritesResponse)
def list_my_favorites(
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # /products/{product_id}보다 먼저 등록해야 "favorites"가 product_id로
    # 오인돼 매칭되지 않는다 (경로 세그먼트 수가 같아 등록 순서가 중요).
    return service.list_my_favorites(db, user, page, size)


@router.get("/products/mine", response_model=schema.ProductListResponse)
def list_my_products(
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # /products/{product_id}보다 먼저 등록해야 "mine"이 product_id로
    # 오인돼 매칭되지 않는다 (favorites와 동일한 이유).
    return service.list_products(db, None, None, None, None, page, size, created_by=user.id)


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


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.delete_product(db, user, product_id)


@router.post("/products/{product_id}/favorite", response_model=schema.FavoriteToggleResponse)
def add_favorite(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.add_favorite(db, user, product_id)


@router.delete("/products/{product_id}/favorite", response_model=schema.FavoriteToggleResponse)
def remove_favorite(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.remove_favorite(db, user, product_id)


@router.post("/analyses", response_model=schema.AnalysisCreated, status_code=status.HTTP_201_CREATED)
def create_analysis(
    body: schema.AnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.create_analysis(db, user, body)


@router.get("/analyses/{analysis_id}/similar", response_model=list[schema.SimilarTransactionItem])
def get_similar_transactions(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_similar_transactions(db, user, analysis_id)


@router.get("/analyses/{analysis_id}/price-range", response_model=schema.PriceRangeResponse)
def get_price_range(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_price_range(db, user, analysis_id)


@router.get("/analyses/{analysis_id}/frequency", response_model=schema.FrequencyResponse)
def get_frequency(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_frequency(db, user, analysis_id)


@router.get("/analyses/{analysis_id}/evidence", response_model=schema.EvidenceResponse)
def get_evidence(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_evidence(db, user, analysis_id)
