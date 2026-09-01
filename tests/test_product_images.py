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
from app.models.product_image import ProductImage
from app.models.region import Region
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
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

        # 1) presign: object_key는 products/{id}/ 아래, 지원 형식만 허용
        presigned = trade_service.presign_product_image(
            db, owner, product.id, ImagePresignRequest(filename="a.jpg", content_type="image/jpeg")
        )
        assert presigned.object_key.startswith(f"products/{product.id}/")
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

        # 2) register: 순서대로 sort_order 부여, 다른 상품 키는 거부
        key1 = presigned.object_key
        second = trade_service.presign_product_image(
            db, owner, product.id, ImagePresignRequest(filename="b.png", content_type="image/png")
        )
        key2 = second.object_key

        result = trade_service.register_product_images(db, owner, product.id, [key1, key2])
        assert [img.sort_order for img in result.images] == [0, 1]
        assert result.images[0].image_url == storage.public_url(key1)

        try:
            trade_service.register_product_images(db, owner, product.id, ["products/9999/x.jpg"])
            raise AssertionError("다른 상품 키 등록은 막혀야 한다")
        except AppError:
            pass

        # 목록/상세에 썸네일·이미지 목록이 반영되는지
        detail = trade_service.get_product_detail(db, product.id)
        assert detail.thumbnail_url == storage.public_url(key1)
        assert len(detail.images) == 2

        listed = trade_service.list_products(db, region.id, None, None, None, page=1, size=20)
        assert listed.items[0].thumbnail_url == storage.public_url(key1)

        # 3) delete: 권한/존재 검증 + 실제 삭제(네트워크는 no-op으로 대체)
        image_id = result.images[1].id
        try:
            trade_service.delete_product_image(db, other, product.id, image_id)
            raise AssertionError("타인 상품 이미지 삭제는 403이어야 한다")
        except PermissionDeniedError:
            pass

        try:
            trade_service.delete_product_image(db, owner, product.id, -1)
            raise AssertionError("없는 이미지 삭제는 404여야 한다")
        except NotFoundError:
            pass

        original_delete_object = storage.delete_object
        storage.delete_object = lambda object_key: None  # 실 NCP 호출 없이 DB 정리만 검증
        try:
            trade_service.delete_product_image(db, owner, product.id, image_id)
        finally:
            storage.delete_object = original_delete_object
        assert db.get(ProductImage, image_id) is None
        assert len(trade_service.get_product_detail(db, product.id).images) == 1

        print("product-images self-check OK")
    finally:
        if product_id is not None:
            db.query(ProductImage).filter_by(product_id=product_id).delete()
            db.query(Product).filter_by(id=product_id).delete()
        db.delete(owner)
        db.delete(other)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
