from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.trades import schema
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatRoom
from app.models.product import Product
from app.models.region import Region
from app.models.user import User


def create_product(db: Session, user: User, data: schema.ProductCreateRequest) -> Product:
    if user.region_id is None:
        raise AppError("활동동네를 먼저 설정해주세요.")

    product = Product(
        title=data.title,
        category=data.category,
        desired_price=data.desired_price,
        region_id=user.region_id,
        created_by=user.id,
        trade_status="SALE",
        trade_type=data.trade_type,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _to_list_item(product: Product, dong_name: str, chat_count: int) -> schema.ProductListItem:
    return schema.ProductListItem(
        id=product.id,
        title=product.title,
        neighborhood_name=dong_name,
        created_at=product.created_at,
        price=product.desired_price,
        trade_status=product.trade_status,
        trade_type=product.trade_type,
        chat_count=chat_count,
        favorite_count=0,  # 관심수 저장 테이블 없음 — 필요해지면 별도 TASK
    )


def list_products(
    db: Session,
    region_id: int | None,
    category: str | None,
    trade_status: str | None,
    q: str | None,
    page: int,
    size: int,
) -> schema.ProductListResponse:
    chat_count_subq = (
        select(ChatRoom.product_id, func.count(ChatRoom.id).label("chat_count"))
        .group_by(ChatRoom.product_id)
        .subquery()
    )

    query = (
        db.query(Product, Region.dong_name, chat_count_subq.c.chat_count)
        .join(Region, Product.region_id == Region.id)
        .outerjoin(chat_count_subq, chat_count_subq.c.product_id == Product.id)
    )
    if region_id is not None:
        query = query.filter(Product.region_id == region_id)
    if category is not None:
        query = query.filter(Product.category == category)
    if trade_status is not None:
        query = query.filter(Product.trade_status == trade_status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.title.ilike(like), Product.search_keyword.ilike(like)))

    total = query.count()
    rows = (
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [_to_list_item(p, dong_name, chat_count or 0) for p, dong_name, chat_count in rows]
    return schema.ProductListResponse(items=items, total=total)


def get_product_detail(db: Session, product_id: int) -> schema.ProductDetailResponse:
    row = (
        db.query(Product, Region.dong_name)
        .join(Region, Product.region_id == Region.id)
        .filter(Product.id == product_id)
        .first()
    )
    if row is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    product, dong_name = row
    chat_count = db.query(func.count(ChatRoom.id)).filter(ChatRoom.product_id == product.id).scalar()
    item = _to_list_item(product, dong_name, chat_count or 0)
    return schema.ProductDetailResponse(
        **item.model_dump(), category=product.category, search_keyword=product.search_keyword
    )


def update_product_status(db: Session, user: User, product_id: int, trade_status: str) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by != user.id:
        raise PermissionDeniedError("본인 상품만 상태를 변경할 수 있습니다.")
    product.trade_status = trade_status
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, user: User, product_id: int, data: schema.ProductUpdateRequest) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by != user.id:
        raise PermissionDeniedError("본인 상품만 수정할 수 있습니다.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
