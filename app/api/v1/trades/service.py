import statistics
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.trades import schema
from app.core import storage
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.analysis import Analysis, AnalysisResult
from app.models.chat import ChatRoom
from app.models.favorite import ProductFavorite
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.region import Region
from app.models.transaction import Transaction
from app.models.user import User


def create_product(db: Session, user: User, data: schema.ProductCreateRequest) -> Product:
    if user.region_id is None:
        raise AppError("활동동네를 먼저 설정해주세요.")

    product = Product(
        title=data.title,
        category=data.category,
        desired_price=data.desired_price,
        description=data.description,
        detail_category=data.detail_category,
        trade_place=data.trade_place,
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
        view_count=product.view_count,
        interest_count=product.interest_count,
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
    created_by: int | None = None,
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
    if created_by is not None:
        query = query.filter(Product.created_by == created_by)

    total = query.count()
    rows = (
        # 크롤링 seed 데이터는 created_at이 날짜 단위(시분초 없음)라 같은 날짜인
        # 행이 수천 건씩 동률 — id를 2차 정렬키로 안 주면 OFFSET 페이지네이션에서
        # 동률 행 순서가 매 요청마다 달라져 페이지 간 중복/누락이 생김.
        query.order_by(Product.created_at.desc(), Product.id.desc())
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
        **item.model_dump(),
        category=product.category,
        detail_category=product.detail_category,
        search_keyword=product.search_keyword,
        description=product.description,
        trade_place=product.trade_place,
        seller_nickname=product.seller_nickname,
        seller_manner_temp=(
            float(product.seller_manner_temp) if product.seller_manner_temp is not None else None
        ),
        images=images,
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


def delete_product(db: Session, user: User, product_id: int) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by != user.id:
        raise PermissionDeniedError("본인 상품만 삭제할 수 있습니다.")

    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    for image in images:
        storage.delete_object(image.object_key)
    db.query(ProductImage).filter(ProductImage.product_id == product_id).delete()
    db.query(ProductFavorite).filter(ProductFavorite.product_id == product_id).delete()
    # 채팅 기록은 보존하고 상품 참조만 끊는다 (ChatRoom.product_id는 nullable).
    db.query(ChatRoom).filter(ChatRoom.product_id == product_id).update({ChatRoom.product_id: None})
    db.delete(product)
    db.commit()


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


# --------------------------------------------------------------------------
# 가격분석 (docs/issue/03-trades.md)
# --------------------------------------------------------------------------

# PRD에 거래빈도 산정 기준기간이 명시돼 있지 않아 임의 기본값(3개월)으로
# 상수화 — 필요해지면 이 값만 조정. 유사거래/가격범위/근거도 "동일 표본"
# 요건(TASK-02-05 DoD)을 위해 같은 윈도우를 공유한다.
FREQUENCY_WINDOW_MONTHS = 3
EVIDENCE_SAMPLE_SIZE = 5


def _frequency_grade(sample_count: int) -> str:
    if sample_count >= 30:
        return "많음"
    if sample_count >= 10:
        return "보통"
    if sample_count >= 3:
        return "낮음"
    return "산정불가"


def _find_similar_transactions(db: Session, analysis: Analysis) -> list[Transaction]:
    product = db.get(Product, analysis.product_id)
    window_start = date.today() - timedelta(days=FREQUENCY_WINDOW_MONTHS * 30)
    base = db.query(Transaction).filter(
        Transaction.region_id == analysis.region_id,
        Transaction.category == product.category,
        Transaction.listed_at >= window_start,
    )
    # 유사도 1차 판정: 제목 부분일치로 좁혀보고, 매칭이 하나도 없으면
    # 카테고리+지역만으로 폴백 (임베딩 기반 유사도는 과설계 — 필요해지면 후순위 도입).
    if product.title:
        keyword_matches = base.filter(Transaction.product_title.ilike(f"%{product.title}%")).all()
        if keyword_matches:
            return keyword_matches
    return base.all()


def _region_names(db: Session, region_ids: set[int]) -> dict[int, str]:
    region_ids = {r for r in region_ids if r is not None}
    if not region_ids:
        return {}
    return {r.id: r.dong_name for r in db.query(Region).filter(Region.id.in_(region_ids)).all()}


def _compute_analysis_result(db: Session, analysis: Analysis) -> AnalysisResult:
    transactions = _find_similar_transactions(db, analysis)
    sample_count = len(transactions)
    prices = sorted(t.price for t in transactions if t.price is not None)

    price_min = price_max = None
    if len(prices) >= 3:
        q1, _, q3 = statistics.quantiles(prices, n=4)
        price_min, price_max = round(q1), round(q3)

    avg_chat = statistics.fmean(t.chat_count for t in transactions) if transactions else 0.0
    avg_interest = statistics.fmean(t.interest_count for t in transactions) if transactions else 0.0

    sample = sorted(transactions, key=lambda t: t.listed_at, reverse=True)[:EVIDENCE_SAMPLE_SIZE]
    region_names = _region_names(db, {t.region_id for t in sample})
    evidence_json = {
        "avg_chat_count": avg_chat,
        "avg_interest_count": avg_interest,
        "sample_transactions": [
            {
                "product_title": t.product_title,
                "price": t.price,
                "listed_at": t.listed_at.isoformat(),
                "region_name": region_names.get(t.region_id),
            }
            for t in sample
        ],
    }

    result = db.query(AnalysisResult).filter_by(analysis_id=analysis.id).first()
    if result is None:
        result = AnalysisResult(analysis_id=analysis.id)
        db.add(result)
    result.price_min = price_min
    result.price_max = price_max
    result.frequency_grade = _frequency_grade(sample_count)
    result.sample_count = sample_count
    result.evidence_json = evidence_json
    db.flush()
    return result


def create_analysis(db: Session, user: User, data: schema.AnalysisRequest) -> schema.AnalysisCreated:
    # region_id 미설정 400과 Product row 생성은 create_product 로직 재사용
    # (분석 전용 임시 상품 — docs/ERD.md 0절 "Product 테이블을 mock과 통합").
    product = create_product(
        db,
        user,
        schema.ProductCreateRequest(title=data.product_title, category=data.category, desired_price=data.desired_price),
    )

    analysis = Analysis(product_id=product.id, region_id=user.region_id, requested_by=user.id, status="pending")
    db.add(analysis)
    db.flush()

    _compute_analysis_result(db, analysis)
    analysis.status = "done"
    db.commit()
    db.refresh(analysis)
    return schema.AnalysisCreated(analysis_id=analysis.id)


def _get_owned_analysis(db: Session, user: User, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise NotFoundError("분석 요청을 찾을 수 없습니다.")
    if analysis.requested_by != user.id:
        raise PermissionDeniedError("본인 분석 요청만 조회할 수 있습니다.")
    return analysis


def _get_result(db: Session, analysis: Analysis) -> AnalysisResult:
    result = db.query(AnalysisResult).filter_by(analysis_id=analysis.id).first()
    if result is None:
        raise NotFoundError("분석 결과를 찾을 수 없습니다.")
    return result


def get_similar_transactions(db: Session, user: User, analysis_id: int) -> list[schema.SimilarTransactionItem]:
    analysis = _get_owned_analysis(db, user, analysis_id)
    transactions = _find_similar_transactions(db, analysis)
    region_names = _region_names(db, {t.region_id for t in transactions})
    return [
        schema.SimilarTransactionItem(
            product_title=t.product_title,
            price=t.price,
            listed_at=t.listed_at,
            region_name=region_names.get(t.region_id),
        )
        for t in transactions
    ]


def get_price_range(db: Session, user: User, analysis_id: int) -> schema.PriceRangeResponse:
    analysis = _get_owned_analysis(db, user, analysis_id)
    result = _get_result(db, analysis)
    if result.price_min is None:
        return schema.PriceRangeResponse(status="insufficient_data", sample_count=result.sample_count)
    return schema.PriceRangeResponse(
        status="ok", price_min=result.price_min, price_max=result.price_max, sample_count=result.sample_count
    )


def get_frequency(db: Session, user: User, analysis_id: int) -> schema.FrequencyResponse:
    analysis = _get_owned_analysis(db, user, analysis_id)
    result = _get_result(db, analysis)
    return schema.FrequencyResponse(frequency_grade=result.frequency_grade, sample_count=result.sample_count)


def get_evidence(db: Session, user: User, analysis_id: int) -> schema.EvidenceResponse:
    analysis = _get_owned_analysis(db, user, analysis_id)
    result = _get_result(db, analysis)
    evidence = result.evidence_json or {}
    samples = [
        schema.SimilarTransactionItem(
            product_title=s["product_title"],
            price=s["price"],
            listed_at=date.fromisoformat(s["listed_at"]),
            region_name=s["region_name"],
        )
        for s in evidence.get("sample_transactions", [])
    ]
    return schema.EvidenceResponse(
        sample_count=result.sample_count,
        avg_chat_count=evidence.get("avg_chat_count", 0.0),
        avg_interest_count=evidence.get("avg_interest_count", 0.0),
        sample_transactions=samples,
        computed_at=result.computed_at,
    )
