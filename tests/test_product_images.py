"""중고거래 상품 이미지 업로드(presign → register → delete) 자가 점검.

python -m tests.test_product_images 로 실행. 실 DB에 임시 유저/지역/상품을
만들었다가 끝나면 전부 지운다. presigned URL 생성은 boto3가 로컬에서
서명만 하고 네트워크를 타지 않으므로 NCP 자격증명이 가짜(.env 플레이스홀더)
여도 안전하게 검증 가능하다. 실제 오브젝트 삭제(storage.delete_object)만
네트워크를 타므로 이 자가점검에서는 no-op으로 바꿔치기한다.
"""

from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import ImagePresignRequest, ProductCreateRequest
from app.core import storage
from app.core.db import SessionLocal
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.product import Product
from app.models.region import Region
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    original_delete_object = storage.delete_object
    storage.delete_object = lambda object_key: None  # 실 NCP 호출 없이 검증

    region = Region(
        dong_code="__IMG_SELFCHECK__",
        dong_name="이미지자가검증동",
        gu_name="자가검증구",
        lat=0.0,
        lng=0.0,
    )
    owner = User(
        email="__image_selfcheck_owner__@example.com",
        password_hash=hash_password("x"),
        nickname="owner",
        role=UserRole.USER,
    )
    other = User(
        email="__image_selfcheck_other__@example.com",
        password_hash=hash_password("x"),
        nickname="other",
        role=UserRole.USER,
    )
    db.add_all([region, owner, other])
    db.commit()
    db.refresh(region)
    db.refresh(owner)
    owner.region_id = region.id
    db.commit()
    db.refresh(owner)

    product_id = None
    try:
        product = trade_service.create_product(
            db, owner, ProductCreateRequest(title="테스트 상품", category="기타")
        )
        product_id = product.id

        # 1) presign: object_key는 products/{id}.{ext} 고정, 지원 형식만 허용
        presigned = trade_service.presign_product_image(
            db, owner, product.id, ImagePresignRequest(filename="a.jpg", content_type="image/jpeg")
        )
        assert presigned.object_key == f"products/{product.id}.jpg"
        assert presigned.upload_url.startswith(storage.settings.NCP_ENDPOINT)

        try:
            trade_service.presign_product_image(
                db, owner, product.id, ImagePresignRequest(filename="a.gif", content_type="image/gif")
            )
            raise AssertionError("지원하지 않는 형식은 막혀야 한다")
        except AppError:
            pass

        try:
            trade_service.presign_product_image(
                db, other, product.id, ImagePresignRequest(filename="a.jpg", content_type="image/jpeg")
            )
            raise AssertionError("타인 상품 presign은 403이어야 한다")
        except PermissionDeniedError:
            pass

        try:
            trade_service.presign_product_image(
                db, owner, -1, ImagePresignRequest(filename="a.jpg", content_type="image/jpeg")
            )
            raise AssertionError("없는 상품 presign은 404여야 한다")
        except NotFoundError:
            pass

        # 2) register: 상품당 이미지 1장, 다른 상품 키는 거부, 재등록하면 덮어씀
        key = presigned.object_key
        result = trade_service.register_product_image(db, owner, product.id, key)
        assert result.image_url == storage.public_url(key)

        try:
            trade_service.register_product_image(db, owner, product.id, "products/9999.jpg")
            raise AssertionError("다른 상품 키 등록은 막혀야 한다")
        except AppError:
            pass

        # 목록/상세에 썸네일이 반영되는지
        detail = trade_service.get_product_detail(db, product.id)
        assert detail.thumbnail_url == storage.public_url(key)

        # 상세 조회 시 글쓴이 본인 여부(is_mine) — 수정 버튼 노출 판단용
        assert trade_service.get_product_detail(db, product.id).is_mine is False
        assert trade_service.get_product_detail(db, product.id, owner).is_mine is True
        assert trade_service.get_product_detail(db, product.id, other).is_mine is False

        listed = trade_service.list_products(db, region.id, None, None, None, page=1, size=20)
        assert listed.items[0].thumbnail_url == storage.public_url(key)

        # 3) delete: 권한/존재 검증 + 실제 삭제
        try:
            trade_service.delete_product_image(db, other, product.id)
            raise AssertionError("타인 상품 이미지 삭제는 403이어야 한다")
        except PermissionDeniedError:
            pass

        trade_service.delete_product_image(db, owner, product.id)
        assert db.get(Product, product.id).image_object_key is None
        assert trade_service.get_product_detail(db, product.id).thumbnail_url is None

        try:
            trade_service.delete_product_image(db, owner, product.id)
            raise AssertionError("이미지가 없으면 삭제는 404여야 한다")
        except NotFoundError:
            pass

        print("product-images self-check OK")
    finally:
        storage.delete_object = original_delete_object
        if product_id is not None:
            db.query(Product).filter_by(id=product_id).delete()
        db.delete(owner)
        db.delete(other)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
