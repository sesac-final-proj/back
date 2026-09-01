from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.trades import schema
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatRoom
from app.models.favorite import ProductFavorite
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


def _to_list_item(
    product: Product, dong_name: str, chat_count: int, favorite_count: int
) -> schema.ProductListItem:
    return schema.ProductListItem(
        id=product.id,
        title=product.title,
        neighborhood_name=dong_name,
        created_at=product.created_at,
        price=product.desired_price,
        trade_status=product.trade_status,
        trade_type=product.trade_type,
        chat_count=chat_count,
        favorite_count=favorite_count,
    )


def _favorite_count_subq():
    return (
        select(ProductFavorite.product_id, func.count(ProductFavorite.id).label("favorite_count"))
        .group_by(ProductFavorite.product_id)
        .subquery()
    )


def list_products(
    db: Session,
    region_id: int | None,
    category: str | None,
    trade_status: str | None,
    q: str | None,
    page: int,
    size: int,
    created_by: int | None = None,
) -> schema.ProductListResponse:
    chat_count_subq = (
        select(ChatRoom.product_id, func.count(ChatRoom.id).label("chat_count"))
        .group_by(ChatRoom.product_id)
        .subquery()
    )
    favorite_count_subq = _favorite_count_subq()

    query = (
        db.query(Product, Region.dong_name, chat_count_subq.c.chat_count, favorite_count_subq.c.favorite_count)
        .join(Region, Product.region_id == Region.id)
        .outerjoin(chat_count_subq, chat_count_subq.c.product_id == Product.id)
        .outerjoin(favorite_count_subq, favorite_count_subq.c.product_id == Product.id)
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
    if created_by is not None:
        query = query.filter(Product.created_by == created_by)

    total = query.count()
    rows = (
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        _to_list_item(p, dong_name, chat_count or 0, favorite_count or 0)
        for p, dong_name, chat_count, favorite_count in rows
    ]
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
    favorite_count = (
        db.query(func.count(ProductFavorite.id)).filter(ProductFavorite.product_id == product.id).scalar()
    )
    item = _to_list_item(product, dong_name, chat_count or 0, favorite_count or 0)
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


def _favorite_count(db: Session, product_id: int) -> int:
    return db.query(func.count(ProductFavorite.id)).filter(ProductFavorite.product_id == product_id).scalar() or 0


def add_favorite(db: Session, user: User, product_id: int) -> schema.FavoriteToggleResponse:
    if db.get(Product, product_id) is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")

    existing = (
        db.query(ProductFavorite)
        .filter(ProductFavorite.user_id == user.id, ProductFavorite.product_id == product_id)
        .first()
    )
    if existing is None:
        db.add(ProductFavorite(user_id=user.id, product_id=product_id))
        db.commit()

    return schema.FavoriteToggleResponse(favorited=True, favorite_count=_favorite_count(db, product_id))


def remove_favorite(db: Session, user: User, product_id: int) -> schema.FavoriteToggleResponse:
    if db.get(Product, product_id) is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")

    db.query(ProductFavorite).filter(
        ProductFavorite.user_id == user.id, ProductFavorite.product_id == product_id
    ).delete()
    db.commit()

    return schema.FavoriteToggleResponse(favorited=False, favorite_count=_favorite_count(db, product_id))


def list_my_favorites(db: Session, user: User, page: int, size: int) -> schema.ProductFavoritesResponse:
    chat_count_subq = (
        select(ChatRoom.product_id, func.count(ChatRoom.id).label("chat_count"))
        .group_by(ChatRoom.product_id)
        .subquery()
    )
    favorite_count_subq = _favorite_count_subq()

    query = (
        db.query(Product, Region.dong_name, chat_count_subq.c.chat_count, favorite_count_subq.c.favorite_count)
        .join(ProductFavorite, ProductFavorite.product_id == Product.id)
        .join(Region, Product.region_id == Region.id)
        .outerjoin(chat_count_subq, chat_count_subq.c.product_id == Product.id)
        .outerjoin(favorite_count_subq, favorite_count_subq.c.product_id == Product.id)
        .filter(ProductFavorite.user_id == user.id)
    )
    total = query.count()
    rows = (
        query.order_by(ProductFavorite.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        _to_list_item(p, dong_name, chat_count or 0, favorite_count or 0)
        for p, dong_name, chat_count, favorite_count in rows
    ]
    return schema.ProductFavoritesResponse(items=items, total=total)


def delete_product(db: Session, user: User, product_id: int) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by != user.id:
        raise PermissionDeniedError("본인 상품만 삭제할 수 있습니다.")

    db.query(ProductFavorite).filter(ProductFavorite.product_id == product_id).delete()
    # 채팅 기록은 보존하고 상품 참조만 끊는다 (ChatRoom.product_id는 nullable).
    db.query(ChatRoom).filter(ChatRoom.product_id == product_id).update({ChatRoom.product_id: None})
    db.delete(product)
    db.commit()
