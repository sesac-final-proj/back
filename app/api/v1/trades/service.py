from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.trades import schema
from app.core import storage
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatRoom
from app.models.favorite import ProductFavorite
from app.models.product import Product
from app.models.product_image import ProductImage
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
    product: Product,
    dong_name: str,
    chat_count: int,
    favorite_count: int,
    thumbnail_object_key: str | None = None,
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
        thumbnail_url=storage.public_url(thumbnail_object_key) if thumbnail_object_key else None,
    )


def _favorite_count_subq():
    return (
        select(ProductFavorite.product_id, func.count(ProductFavorite.id).label("favorite_count"))
        .group_by(ProductFavorite.product_id)
        .subquery()
    )


def _thumbnail_subq():
    # product당 sort_order가 가장 앞선 이미지 1장만 (Postgres DISTINCT ON).
    return (
        select(ProductImage.product_id, ProductImage.object_key)
        .distinct(ProductImage.product_id)
        .order_by(ProductImage.product_id, ProductImage.sort_order)
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
) -> schema.ProductListResponse:
    chat_count_subq = (
        select(ChatRoom.product_id, func.count(ChatRoom.id).label("chat_count"))
        .group_by(ChatRoom.product_id)
        .subquery()
    )
    favorite_count_subq = _favorite_count_subq()
    thumbnail_subq = _thumbnail_subq()

    query = (
        db.query(
            Product,
            Region.dong_name,
            chat_count_subq.c.chat_count,
            favorite_count_subq.c.favorite_count,
            thumbnail_subq.c.object_key,
        )
        .join(Region, Product.region_id == Region.id)
        .outerjoin(chat_count_subq, chat_count_subq.c.product_id == Product.id)
        .outerjoin(favorite_count_subq, favorite_count_subq.c.product_id == Product.id)
        .outerjoin(thumbnail_subq, thumbnail_subq.c.product_id == Product.id)
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
    items = [
        _to_list_item(p, dong_name, chat_count or 0, favorite_count or 0, thumbnail_key)
        for p, dong_name, chat_count, favorite_count, thumbnail_key in rows
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
    images = _list_product_images(db, product.id).images
    thumbnail_key = images[0].image_url if images else None
    item = _to_list_item(product, dong_name, chat_count or 0, favorite_count or 0)
    item.thumbnail_url = thumbnail_key
    return schema.ProductDetailResponse(
        **item.model_dump(), category=product.category, search_keyword=product.search_keyword, images=images
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
    thumbnail_subq = _thumbnail_subq()

    query = (
        db.query(
            Product,
            Region.dong_name,
            chat_count_subq.c.chat_count,
            favorite_count_subq.c.favorite_count,
            thumbnail_subq.c.object_key,
        )
        .join(ProductFavorite, ProductFavorite.product_id == Product.id)
        .join(Region, Product.region_id == Region.id)
        .outerjoin(chat_count_subq, chat_count_subq.c.product_id == Product.id)
        .outerjoin(favorite_count_subq, favorite_count_subq.c.product_id == Product.id)
        .outerjoin(thumbnail_subq, thumbnail_subq.c.product_id == Product.id)
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
        _to_list_item(p, dong_name, chat_count or 0, favorite_count or 0, thumbnail_key)
        for p, dong_name, chat_count, favorite_count, thumbnail_key in rows
    ]
    return schema.ProductFavoritesResponse(items=items, total=total)


def _get_owned_product(db: Session, user: User, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by != user.id:
        raise PermissionDeniedError("본인 상품에만 이미지를 등록/삭제할 수 있습니다.")
    return product


def presign_product_image(
    db: Session, user: User, product_id: int, data: schema.ImagePresignRequest
) -> schema.ImagePresignResponse:
    _get_owned_product(db, user, product_id)
    try:
        object_key = storage.build_object_key(product_id, data.content_type)
    except ValueError as e:
        raise AppError(str(e))
    return schema.ImagePresignResponse(
        upload_url=storage.presigned_put_url(object_key, data.content_type),
        object_key=object_key,
        image_url=storage.public_url(object_key),
    )


def _list_product_images(db: Session, product_id: int) -> schema.ProductImagesResponse:
    rows = (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
        .all()
    )
    items = [
        schema.ProductImageItem(id=r.id, image_url=storage.public_url(r.object_key), sort_order=r.sort_order)
        for r in rows
    ]
    return schema.ProductImagesResponse(images=items)


def register_product_images(
    db: Session, user: User, product_id: int, object_keys: list[str]
) -> schema.ProductImagesResponse:
    _get_owned_product(db, user, product_id)

    # presign이 내준 키만 등록 가능 — 다른 상품 폴더의 키를 갖다 붙이는 걸 막는다.
    prefix = f"products/{product_id}/"
    for key in object_keys:
        if not key.startswith(prefix):
            raise AppError("잘못된 이미지 키입니다.")

    next_order = db.query(func.max(ProductImage.sort_order)).filter(ProductImage.product_id == product_id).scalar()
    start = (next_order + 1) if next_order is not None else 0
    for i, key in enumerate(object_keys):
        db.add(ProductImage(product_id=product_id, object_key=key, sort_order=start + i))
    db.commit()

    return _list_product_images(db, product_id)


def delete_product_image(db: Session, user: User, product_id: int, image_id: int) -> None:
    _get_owned_product(db, user, product_id)

    image = db.get(ProductImage, image_id)
    if image is None or image.product_id != product_id:
        raise NotFoundError("이미지를 찾을 수 없습니다.")

    storage.delete_object(image.object_key)
    db.delete(image)
    db.commit()
