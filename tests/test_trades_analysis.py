"""가격분석(유사거래/적정가격/거래빈도/근거, docs/issue/03-trades.md) 자가 점검.

python -m tests.test_trades_analysis 로 실행. 실 DB에 임시 유저/지역/거래
원천데이터를 만들었다가 끝나면 전부 지운다.
"""
from datetime import date, timedelta

from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import AnalysisRequest
from app.core.db import SessionLocal
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.analysis import Analysis, AnalysisResult
from app.models.product import Product
from app.models.region import Region
from app.models.transaction import Transaction
from app.models.user import User, UserRole


def test_frequency_grade_boundaries():
    """TASK-02-04 DoD: 경계값 30/10/3 단위테스트."""
    f = trade_service._frequency_grade
    assert f(30) == "많음" and f(31) == "많음"
    assert f(29) == "보통" and f(10) == "보통"
    assert f(9) == "낮음" and f(3) == "낮음"
    assert f(2) == "산정불가" and f(0) == "산정불가"


def test_price_hint():
    """글쓰기 화면 실시간 시세 힌트 — 모델명(V8/V10)별로 다른 중위값이 잡히는지."""
    db = SessionLocal()
    region = Region(dong_code="__PH_SELFCHECK__", dong_name="힌트검증동", gu_name="힌트검증구", lat=0.0, lng=0.0)
    db.add(region)
    db.commit()
    db.refresh(region)

    def _tx(title: str, price: int) -> Transaction:
        return Transaction(
            product_title=title,
            category="디지털/가전",
            price=price,
            region_id=region.id,
            status="거래완료",
            listed_at=date.today(),
        )

    # 실제 크롤링 데이터와 안 겹치게 고유 마커를 모델명 자리에 박아넣는다
    # (region 필터가 없는 함수라 region으로는 실데이터와 못 나눔).
    v8_kw, v10_kw = "__PH_MODEL_V8__", "__PH_MODEL_V10__"
    rows = [
        _tx(f"다이슨 {v8_kw} 청소기 팝니다", 55000),
        _tx(f"다이슨 {v8_kw} 무선청소기 급처", 60000),
        _tx(f"다이슨 {v8_kw} 미개봉", 65000),
        _tx(f"다이슨 {v10_kw} 청소기", 90000),
        _tx(f"다이슨 {v10_kw} 팝니다 급처", 100000),
        _tx(f"다이슨 {v10_kw} 정품", 110000),
    ]
    db.add_all(rows)
    db.commit()
    try:
        v8 = trade_service.get_price_hint(db, f"다이슨 {v8_kw}", None)
        assert v8.status == "ok" and v8.sample_count == 3
        assert v8.median_price == 60000
        assert v8.price_min == 48000 and v8.price_max == 72000  # ±20%

        v10 = trade_service.get_price_hint(db, f"다이슨 {v10_kw}", None)
        assert v10.status == "ok" and v10.median_price == 100000
        assert v10.median_price != v8.median_price  # 모델별로 구분돼야 함

        empty = trade_service.get_price_hint(db, "존재안하는모델명xyz", None)
        assert empty.status == "insufficient_data" and empty.sample_count == 0

        too_short = trade_service.get_price_hint(db, "다", None)
        assert too_short.status == "insufficient_data"  # 제목 1글자는 조회 자체를 안 함

        # 글쓰기 화면의 category("중고거래" 등 게시판 대분류)는 크롤링 데이터의
        # category("디지털/가전" 등 실제 품목분류)와 어휘가 달라 그대로 필터링하면
        # 항상 0건 — title만으로 폴백돼서 정상 매칭돼야 한다(실사고 재현 케이스).
        mismatched_category = trade_service.get_price_hint(db, f"다이슨 {v8_kw}", "중고거래")
        assert mismatched_category.status == "ok" and mismatched_category.sample_count == 3
        assert mismatched_category.median_price == 60000

        print("price-hint self-check OK")
    finally:
        db.query(Transaction).filter(Transaction.region_id == region.id).delete(synchronize_session=False)
        db.delete(region)
        db.commit()
        db.close()


def main():
    test_frequency_grade_boundaries()
    test_price_hint()

    db = SessionLocal()
    region = Region(
        dong_code="__AN_SELFCHECK__",
        dong_name="분석자가검증동",
        gu_name="자가검증구",
        lat=0.0,
        lng=0.0,
    )
    other_region = Region(
        dong_code="__AN_SELFCHECK_OTH__",
        dong_name="다른동",
        gu_name="자가검증구",
        lat=0.0,
        lng=0.0,
    )
    owner = User(
        email="__analysis_selfcheck_owner__@example.com",
        password_hash=hash_password("x"),
        nickname="owner",
        role=UserRole.USER,
    )
    other = User(
        email="__analysis_selfcheck_other__@example.com",
        password_hash=hash_password("x"),
        nickname="other",
        role=UserRole.USER,
    )
    db.add_all([region, other_region, owner, other])
    db.commit()
    db.refresh(region)
    db.refresh(other_region)
    db.refresh(owner)
    owner.region_id = region.id
    db.commit()
    db.refresh(owner)

    today = date.today()
    transactions = [
        # 같은 지역+카테고리, 윈도우 내 — 유사거래로 잡혀야 함 (가격 3건 이상)
        Transaction(
            product_title="아이폰 13 128GB",
            category="휴대폰",
            price=500000 + i * 10000,
            region_id=region.id,
            status="거래완료",
            chat_count=i,
            interest_count=i * 2,
            view_count=i * 10,
            listed_at=today - timedelta(days=i),
        )
        for i in range(5)
    ]
    transactions += [
        # 다른 카테고리 — 제외돼야 함
        Transaction(
            product_title="원목 책상",
            category="가구",
            price=100000,
            region_id=region.id,
            status="거래완료",
            chat_count=1,
            interest_count=1,
            view_count=1,
            listed_at=today,
        ),
        # 다른 지역 — 제외돼야 함
        Transaction(
            product_title="아이폰 13 128GB",
            category="휴대폰",
            price=999999,
            region_id=other_region.id,
            status="거래완료",
            chat_count=1,
            interest_count=1,
            view_count=1,
            listed_at=today,
        ),
        # 윈도우 밖(3개월 초과) — 제외돼야 함
        Transaction(
            product_title="아이폰 13 128GB",
            category="휴대폰",
            price=100,
            region_id=region.id,
            status="거래완료",
            chat_count=1,
            interest_count=1,
            view_count=1,
            listed_at=today - timedelta(days=200),
        ),
    ]
    db.add_all(transactions)
    db.commit()

    product_id = None
    analysis_id = None
    try:
        try:
            trade_service.create_analysis(db, other, AnalysisRequest(product_title="아이폰 13 128GB", category="휴대폰"))
            raise AssertionError("활동동네 없는데 분석 요청되면 안 된다")
        except AppError:
            pass

        created = trade_service.create_analysis(
            db, owner, AnalysisRequest(product_title="아이폰 13 128GB", category="휴대폰", desired_price=520000)
        )
        analysis_id = created.analysis_id
        analysis = db.get(Analysis, analysis_id)
        product_id = analysis.product_id
        assert analysis.status == "done"

        # 유사거래: 같은지역+같은카테고리 5건만 (다른카테고리/다른지역/윈도우밖 제외)
        similar = trade_service.get_similar_transactions(db, owner, analysis_id)
        assert len(similar) == 5, f"기대 5건, 실제 {len(similar)}건"
        assert all(s.region_name == "분석자가검증동" for s in similar)

        price_range = trade_service.get_price_range(db, owner, analysis_id)
        assert price_range.status == "ok"
        assert price_range.price_min <= price_range.price_max
        assert price_range.sample_count == 5

        frequency = trade_service.get_frequency(db, owner, analysis_id)
        assert frequency.sample_count == 5
        assert frequency.frequency_grade == "낮음"  # 3~9건

        evidence = trade_service.get_evidence(db, owner, analysis_id)
        assert evidence.sample_count == 5
        assert len(evidence.sample_transactions) == 5  # EVIDENCE_SAMPLE_SIZE=5, 표본도 5건이라 전부
        assert evidence.avg_chat_count == sum(range(5)) / 5

        # 표본 부족 케이스: 새 카테고리로 분석하면 유사거래 0건 -> insufficient_data / 산정불가
        empty_analysis = trade_service.create_analysis(
            db, owner, AnalysisRequest(product_title="존재안하는상품", category="없는카테고리")
        )
        empty_price = trade_service.get_price_range(db, owner, empty_analysis.analysis_id)
        assert empty_price.status == "insufficient_data" and empty_price.sample_count == 0
        empty_freq = trade_service.get_frequency(db, owner, empty_analysis.analysis_id)
        assert empty_freq.frequency_grade == "산정불가"
        # 정리용으로 기록
        db.query(AnalysisResult).filter_by(analysis_id=empty_analysis.analysis_id).delete()
        empty_product_id = db.get(Analysis, empty_analysis.analysis_id).product_id
        db.query(Analysis).filter_by(id=empty_analysis.analysis_id).delete()
        db.query(Product).filter_by(id=empty_product_id).delete()
        db.commit()

        # 권한: 본인 분석 아니면 403, 없는 분석은 404
        try:
            trade_service.get_price_range(db, other, analysis_id)
            raise AssertionError("타인 분석 조회는 403이어야 한다")
        except PermissionDeniedError:
            pass

        try:
            trade_service.get_price_range(db, owner, -1)
            raise AssertionError("없는 분석 조회는 404여야 한다")
        except NotFoundError:
            pass

        print("trades-analysis self-check OK")
    finally:
        if analysis_id is not None:
            db.query(AnalysisResult).filter_by(analysis_id=analysis_id).delete()
            db.query(Analysis).filter_by(id=analysis_id).delete()
        if product_id is not None:
            db.query(Product).filter_by(id=product_id).delete()
        db.query(Transaction).filter(Transaction.region_id.in_([region.id, other_region.id])).delete(
            synchronize_session=False
        )
        db.delete(owner)
        db.delete(other)
        db.delete(region)
        db.delete(other_region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
