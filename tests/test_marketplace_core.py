"""상품/채팅 기본 마켓 기능(10-marketplace-core.md) 자가 점검.

python -m tests.test_marketplace_core 로 실행. 실 DB에 임시 유저/지역/
상품/채팅방을 만들었다가 끝나면 전부 지운다 (스키마 변경 없음, 일반
CRUD만 수행).
"""

from fastapi import HTTPException

from app.api.v1.chats import service as chat_service
from app.api.v1.chats.schema import ChatRoomCreateRequest, MessageCreateRequest
from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import ProductCreateRequest, ProductStatusUpdateRequest, ProductUpdateRequest
from app.core.db import SessionLocal
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.favorite import ProductFavorite
from app.models.product import Product
from app.models.region import Region
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    region = Region(
        dong_code="__SELFCHECK__",
        dong_name="자가검증동",
        gu_name="자가검증구",
        lat=0.0,
        lng=0.0,
    )
    owner = User(
        email="__marketplace_selfcheck_owner__@example.com",
        password_hash=hash_password("x"),
        nickname="owner",
        role=UserRole.USER,
    )
    other = User(
        email="__marketplace_selfcheck_other__@example.com",
        password_hash=hash_password("x"),
        nickname="other",
        role=UserRole.USER,
    )
    db.add_all([region, owner, other])
    db.commit()
    db.refresh(region)
    db.refresh(owner)
    db.refresh(other)
    owner.region_id = region.id
    db.commit()
    db.refresh(owner)

    product_id = None
    room_id = None
    try:
        # 활동동네 없는 유저는 상품 등록 불가
        try:
            trade_service.create_product(db, other, ProductCreateRequest(title="x", category="c"))
            raise AssertionError("활동동네 없는데 등록되면 안 된다")
        except AppError:
            pass

        product = trade_service.create_product(
            db, owner, ProductCreateRequest(title="원목 사이드 테이블", category="가구", desired_price=28000)
        )
        product_id = product.id
        assert product.trade_status == "SALE"

        page = trade_service.list_products(db, region.id, None, None, None, page=1, size=20)
        assert page.total == 1
        assert page.items[0].neighborhood_name == "자가검증동"
        assert page.items[0].favorite_count == 0

        detail = trade_service.get_product_detail(db, product.id)
        assert detail.category == "가구"

        try:
            trade_service.get_product_detail(db, -1)
            raise AssertionError("없는 상품이면 404여야 한다")
        except NotFoundError:
            pass

        try:
            trade_service.update_product_status(db, other, product.id, "SOLD")
            raise AssertionError("타인 소유 상품 상태변경은 403이어야 한다")
        except PermissionDeniedError:
            pass

        trade_service.update_product_status(db, owner, product.id, "RESERVED")
        assert trade_service.get_product_detail(db, product.id).trade_status == "RESERVED"

        try:
            trade_service.update_product(db, other, product.id, ProductUpdateRequest(title="가로채기"))
            raise AssertionError("타인 소유 상품 수정은 403이어야 한다")
        except PermissionDeniedError:
            pass

        trade_service.update_product(
            db, owner, product.id, ProductUpdateRequest(title="원목 사이드 테이블(가격내림)", desired_price=20000)
        )
        updated = trade_service.get_product_detail(db, product.id)
        assert updated.title == "원목 사이드 테이블(가격내림)"
        assert updated.price == 20000
        assert updated.category == "가구"  # 안 건드린 필드는 유지

        # 실제 크롤링 데이터가 products에 같이 들어있을 수 있어(scripts/seed_products.py)
        # region_id로 이 자가검증 전용 지역(region.id)에 스코프를 좁힌다 — 실데이터는
        # 이 region_id를 절대 못 가지니 어떤 단어를 검색하든 서로 충돌할 일이 없다.
        found = trade_service.list_products(db, region.id, None, None, "사이드", page=1, size=20)
        assert found.total == 1
        not_found = trade_service.list_products(db, region.id, None, None, "냉장고", page=1, size=20)
        assert not_found.total == 0

        # 내 상품 목록
        mine_owner = trade_service.list_products(db, None, None, None, None, page=1, size=20, created_by=owner.id)
        assert mine_owner.total == 1 and mine_owner.items[0].id == product.id
        mine_other = trade_service.list_products(db, None, None, None, None, page=1, size=20, created_by=other.id)
        assert mine_other.total == 0

        # 채팅방: TRADE인데 product_id 없으면 DTO validator가 이미 막음
        try:
            ChatRoomCreateRequest(type="TRADE")
            raise AssertionError("product_id 없는 TRADE 요청은 막혀야 한다")
        except ValueError:
            pass

        try:
            chat_service.create_chat_room(db, other, ChatRoomCreateRequest(type="COMMUNITY"))
            raise AssertionError("COMMUNITY 타입은 아직 미지원, AppError여야 한다")
        except AppError:
            pass

        room = chat_service.create_chat_room(
            db, other, ChatRoomCreateRequest(type="TRADE", product_id=product.id)
        )
        room_id = room.id
        assert room.title == product.title
        assert room.unread_count == 0

        rooms_page = chat_service.list_my_chat_rooms(db, other, page=1, size=20)
        assert rooms_page.total == 1
        assert rooms_page.items[0].id == room.id

        rooms_page_owner = chat_service.list_my_chat_rooms(db, owner, page=1, size=20)
        assert rooms_page_owner.total == 0  # 개설자(other)만 참여자로 등록됨

        # 찜
        fav = trade_service.add_favorite(db, other, product.id)
        assert fav.favorited is True and fav.favorite_count == 1
        fav_again = trade_service.add_favorite(db, other, product.id)  # 중복 찜 -> 그대로 1
        assert fav_again.favorite_count == 1
        assert trade_service.get_product_detail(db, product.id).favorite_count == 1

        my_favs = trade_service.list_my_favorites(db, other, page=1, size=20)
        assert my_favs.total == 1 and my_favs.items[0].id == product.id

        unfav = trade_service.remove_favorite(db, other, product.id)
        assert unfav.favorited is False and unfav.favorite_count == 0
        assert trade_service.list_my_favorites(db, other, page=1, size=20).total == 0

        try:
            trade_service.add_favorite(db, other, -1)
            raise AssertionError("없는 상품 찜은 404여야 한다")
        except NotFoundError:
            pass

        # 채팅 메시지
        try:
            chat_service.send_message(db, owner, room.id, MessageCreateRequest(content="야"))
            raise AssertionError("참여자 아닌데 메시지 보내면 403이어야 한다")
        except PermissionDeniedError:
            pass

        msg = chat_service.send_message(
            db, other, room.id, MessageCreateRequest(content="아직 판매 중인가요?")
        )
        assert msg.content == "아직 판매 중인가요?"

        try:
            chat_service.list_messages(db, owner, room.id, page=1, size=20)
            raise AssertionError("참여자 아닌데 메시지 조회하면 403이어야 한다")
        except PermissionDeniedError:
            pass

        try:
            chat_service.list_messages(db, other, -1, page=1, size=20)
            raise AssertionError("없는 채팅방 조회는 404여야 한다")
        except NotFoundError:
            pass

        msgs = chat_service.list_messages(db, other, room.id, page=1, size=20)
        assert msgs.total == 1 and msgs.items[0].content == "아직 판매 중인가요?"

        room_after = db.get(ChatRoom, room.id)
        assert room_after.last_message == "아직 판매 중인가요?"

        # 삭제
        try:
            trade_service.delete_product(db, other, product.id)
            raise AssertionError("타인 소유 상품 삭제는 403이어야 한다")
        except PermissionDeniedError:
            pass

        trade_service.delete_product(db, owner, product.id)
        try:
            trade_service.get_product_detail(db, product.id)
            raise AssertionError("삭제된 상품 조회는 404여야 한다")
        except NotFoundError:
            pass

        # 삭제 후에도 채팅방은 남아있고, product_id만 NULL로 끊긴다
        room_after_delete = db.get(ChatRoom, room.id)
        assert room_after_delete is not None
        assert room_after_delete.product_id is None

        try:
            trade_service.delete_product(db, owner, -1)
            raise AssertionError("없는 상품 삭제는 404여야 한다")
        except NotFoundError:
            pass

        product_id = None  # 이미 삭제됨 -> finally에서 중복 처리 안 하도록

        print("marketplace-core self-check OK")
    finally:
        if room_id is not None:
            db.query(ChatMessage).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoomParticipant).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoom).filter_by(id=room_id).delete()
        if product_id is not None:
            db.query(ProductFavorite).filter_by(product_id=product_id).delete()
            db.query(Product).filter_by(id=product_id).delete()
        db.delete(owner)
        db.delete(other)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
