"""내 동네 다중 설정(user_regions) 자가 점검. python -m tests.test_user_regions 로 실행.

docs/issue/11-multi-region.md TASK-11-01~05 DoD를 그대로 따라간다. 실 DB에
임시 유저/지역을 만들었다가 끝나면 전부 지운다.
"""
from fastapi import HTTPException

from app.api.v1.auth import service as auth_service
from app.api.v1.auth.schema import RegionUpdateRequest, UserRegionCreateRequest, UserRegionUpdateRequest
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.region import Region
from app.models.user import User, UserRole
from app.models.user_region import UserRegion


def main():
    db = SessionLocal()

    region_a = Region(dong_code="__UR_SELFCHECK_A__", dong_name="가동", gu_name="자가검증구", lat=0.0, lng=0.0)
    region_b = Region(dong_code="__UR_SELFCHECK_B__", dong_name="나동", gu_name="자가검증구", lat=0.0, lng=0.0)
    region_c = Region(dong_code="__UR_SELFCHECK_C__", dong_name="다동", gu_name="자가검증구", lat=0.0, lng=0.0)
    region_d = Region(dong_code="__UR_SELFCHECK_D__", dong_name="라동", gu_name="자가검증구", lat=0.0, lng=0.0)
    user = User(
        email="__user_region_selfcheck__@example.com",
        password_hash=hash_password("x"),
        nickname="ur_selfcheck",
        role=UserRole.USER,
    )
    db.add_all([region_a, region_b, region_c, region_d, user])
    db.commit()
    db.refresh(region_a)
    db.refresh(region_b)
    db.refresh(region_c)
    db.refresh(region_d)
    db.refresh(user)

    try:
        # 1) 첫 등록 — is_primary 명시 안 해도 무조건 대표로
        item_a = auth_service.add_user_region(
            db, user, UserRegionCreateRequest(region_id=region_a.id, radius_m=500)
        )
        assert item_a.is_primary is True
        db.refresh(user)
        assert user.region_id == region_a.id and user.radius_m == 500

        listed = auth_service.list_user_regions(db, user)
        assert len(listed.items) == 1 and listed.items[0].is_primary is True

        # 2) 두 번째 등록(대표 아님) — 목록 2개, 기존 대표 유지
        item_b = auth_service.add_user_region(
            db, user, UserRegionCreateRequest(region_id=region_b.id, radius_m=1000, is_primary=False)
        )
        assert item_b.is_primary is False
        listed = auth_service.list_user_regions(db, user)
        assert len(listed.items) == 2 and listed.items[0].region_id == region_a.id  # primary가 앞

        # 3) 3번째 등록 시도 → 409
        try:
            auth_service.add_user_region(db, user, UserRegionCreateRequest(region_id=region_c.id, radius_m=500))
            raise AssertionError("3개째 등록은 409여야 한다")
        except HTTPException as e:
            assert e.status_code == 409

        # 4) 중복 동네 재등록 → 409, 그것도 "이미 2개 등록했어요"가 아니라 "이미 등록된
        # 동네입니다"여야 한다 — 이미 2개 다 찬 상태에서 그중 하나를 다시 고른 거라
        # 인원수 초과 메시지가 뜨면 "분명 등록했는데 왜 안 되냐"는 혼란을 준다.
        try:
            auth_service.add_user_region(db, user, UserRegionCreateRequest(region_id=region_a.id, radius_m=500))
            raise AssertionError("중복 동네 등록은 409여야 한다")
        except HTTPException as e:
            assert e.status_code == 409
            assert e.detail == "이미 등록된 동네입니다."

        # 5) 없는 지역 → 404
        try:
            auth_service.add_user_region(db, user, UserRegionCreateRequest(region_id=-1, radius_m=500))
            raise AssertionError("없는 지역은 404여야 한다")
        except HTTPException as e:
            assert e.status_code == 404

        # 6) 대표 전환 — B가 대표로, A는 내려감
        switched = auth_service.set_primary_user_region(
            db, user, region_b.id, UserRegionUpdateRequest(is_primary=True)
        )
        assert switched.is_primary is True
        listed = auth_service.list_user_regions(db, user)
        assert {(i.region_id, i.is_primary) for i in listed.items} == {
            (region_a.id, False),
            (region_b.id, True),
        }
        db.refresh(user)
        assert user.region_id == region_b.id and user.radius_m == 1000

        # 7) 등록 안 된 동네 전환 시도 → 404
        try:
            auth_service.set_primary_user_region(db, user, region_c.id, UserRegionUpdateRequest(is_primary=True))
            raise AssertionError("등록 안 된 동네 전환은 404여야 한다")
        except HTTPException as e:
            assert e.status_code == 404

        # 8) 대표(B) 삭제 → 남은 A가 자동 승격, User 캐시도 A로
        auth_service.remove_user_region(db, user, region_b.id)
        listed = auth_service.list_user_regions(db, user)
        assert len(listed.items) == 1 and listed.items[0].region_id == region_a.id and listed.items[0].is_primary
        db.refresh(user)
        assert user.region_id == region_a.id and user.radius_m == 500

        # 9) 마지막 1개 삭제 시도 → 400
        try:
            auth_service.remove_user_region(db, user, region_a.id)
            raise AssertionError("마지막 동네 삭제는 400이어야 한다")
        except HTTPException as e:
            assert e.status_code == 400

        # 10) 하위 호환 PUT /me/region — 새 동네면 추가되고 대표가 된다
        auth_service.update_region(db, user, RegionUpdateRequest(region_id=region_b.id, radius_m=2000))
        listed = auth_service.list_user_regions(db, user)
        assert {(i.region_id, i.is_primary, i.radius_m) for i in listed.items} == {
            (region_a.id, False, 500),
            (region_b.id, True, 2000),
        }
        db.refresh(user)
        assert user.region_id == region_b.id and user.radius_m == 2000

        # 11) 하위 호환 PUT /me/region — 이미 등록된 동네면 대표 전환 + radius 갱신
        auth_service.update_region(db, user, RegionUpdateRequest(region_id=region_a.id, radius_m=999))
        listed = auth_service.list_user_regions(db, user)
        assert {(i.region_id, i.is_primary, i.radius_m) for i in listed.items} == {
            (region_a.id, True, 999),
            (region_b.id, False, 2000),
        }
        db.refresh(user)
        assert user.region_id == region_a.id and user.radius_m == 999

        # 12) 하위 호환 PUT /me/region — 이미 2개(a,b) 다 찬 상태에서 완전히 새로운
        # 3번째 동네(d)로 바꿔도 409 없이 성공해야 한다(버그 리포트: "동네 2개 등록했다"는
        # 에러가 뜨는데 정작 프론트엔 여러 동네 등록 UI가 없어서 사용자가 이유를 모름).
        # 대표 아니던 슬롯(b)이 자동으로 밀려나고 그 자리에 d가 대표로 들어간다.
        auth_service.update_region(db, user, RegionUpdateRequest(region_id=region_d.id, radius_m=1500))
        listed = auth_service.list_user_regions(db, user)
        assert {(i.region_id, i.is_primary) for i in listed.items} == {
            (region_a.id, False),
            (region_d.id, True),
        }
        db.refresh(user)
        assert user.region_id == region_d.id and user.radius_m == 1500

        print("user-regions self-check OK")
    finally:
        db.query(UserRegion).filter_by(user_id=user.id).delete()
        db.delete(user)
        db.delete(region_a)
        db.delete(region_b)
        db.delete(region_c)
        db.delete(region_d)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
